"""
DSA AutoGrader — Grading Engine.

Pipeline cham diem:
  1. Static Analysis (AST)
  2. Lay tieu chi tu ngan hang bai tap (external API)
  3. Code Review (Gemini) voi rubric dong
  4. Score Merging & Normalization
  5. Plagiarism Detection
"""

import asyncio
import json
import re
import logging
from typing import Any, Dict, List

from google import genai
from google.genai import types

from app.core.config import (
    GEMINI_API_KEY,
    AI_MODEL_NAME,
    AI_MODEL_TEMPERATURE,
    AI_MAX_OUTPUT_TOKENS,
    PASS_SCORE_THRESHOLD,
    PLAGIARISM_THRESHOLD,
)
from app.services.analyzer import ASTAnalyzer
from app.utils.helpers import fetch_problem_from_bank

logger = logging.getLogger("dsa.grader")


class AIGrader:
    """Automated Code Review & Grading Engine."""

    def __init__(self) -> None:
        self.analyzer = ASTAnalyzer()
        self.client = None
        self._configure_ai()

    # ═══════════════════════════════════════════
    #  Public API
    # ═══════════════════════════════════════════

    async def grade_auto(
        self,
        code: str,
        filename: str,
        topic: str | None = None,
    ) -> Dict[str, Any]:
        """Main Pipeline: Cham diem tu dong mot file Python."""
        loop = asyncio.get_running_loop()

        # Step 1: Static Analysis
        ast_result = await loop.run_in_executor(
            None, self.analyzer.analyze_code, code, filename, topic
        )

        if not ast_result.get("valid_score"):
            logger.warning("Analysis failed for '%s': %s", filename, ast_result["notes"])
            return ast_result

        # Step 2: Lay tieu chi tu ngan hang bai tap
        problem_data = await loop.run_in_executor(
            None, fetch_problem_from_bank, topic or filename
        )

        # Step 3: Review voi rubric dong (neu co)
        ai_result = await self._ai_review(code, ast_result, problem_data)

        # Step 4: Merge
        return self._merge_results(ast_result, ai_result, problem_data)

    def check_plagiarism(self, results: List[Dict]) -> List[Dict]:
        """Phat hien dao van dua tren AST Fingerprint (Jaccard Similarity)."""
        n = len(results)
        if n < 2:
            return results

        for i in range(n):
            results[i].setdefault("notes", [])
            fp_i = results[i].get("fingerprint")
            if not fp_i or not isinstance(fp_i, set):
                continue

            for j in range(i + 1, n):
                results[j].setdefault("notes", [])
                fp_j = results[j].get("fingerprint")
                if not fp_j or not isinstance(fp_j, set):
                    continue

                intersection = len(fp_i & fp_j)
                union = len(fp_i | fp_j)
                similarity = intersection / union if union > 0 else 0

                if similarity > PLAGIARISM_THRESHOLD:
                    pct = f"{similarity:.0%}"
                    name_i = results[i].get("filename", "?")
                    name_j = results[j].get("filename", "?")

                    msg_i = f"CANH BAO: Trung lap {pct} voi bai cua {name_j}"
                    msg_j = f"CANH BAO: Trung lap {pct} voi bai cua {name_i}"

                    if msg_i not in results[i]["notes"]:
                        results[i]["notes"].append(msg_i)
                        results[i]["status"] = "FLAG"
                    if msg_j not in results[j]["notes"]:
                        results[j]["notes"].append(msg_j)
                        results[j]["status"] = "FLAG"

                    logger.warning(
                        "Plagiarism: '%s' <-> '%s' (%.0f%%)",
                        name_i, name_j, similarity * 100,
                    )

        for r in results:
            r.pop("fingerprint", None)
            r.pop("features", None)

        return results

    # ═══════════════════════════════════════════
    #  AI Configuration
    # ═══════════════════════════════════════════

    def _configure_ai(self) -> None:
        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set. AI Review will use fallback scoring.")
            return
        try:
            self.client = genai.Client(api_key=GEMINI_API_KEY)
            logger.info("GenAI Client configured with model '%s'.", AI_MODEL_NAME)
        except Exception as exc:
            logger.error("AI Client config failed: %s", exc)
            self.client = None

    # ═══════════════════════════════════════════
    #  AI Review
    # ═══════════════════════════════════════════

    async def _ai_review(
        self,
        code: str,
        ast_data: Dict,
        problem: Dict | None,
    ) -> Dict[str, Any]:
        if not self.client:
            return self._use_fallback(ast_data, problem)

        prompt = self._build_prompt(code, ast_data, problem)

        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_content(
                    model=AI_MODEL_NAME,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=AI_MODEL_TEMPERATURE,
                        top_p=0.95,
                        top_k=40,
                        max_output_tokens=AI_MAX_OUTPUT_TOKENS,
                    ),
                ),
            )
            return self._parse_ai_response(response.text, ast_data, problem)
        except Exception as exc:
            logger.error("AI Generation failed: %s", exc)
            return self._use_fallback(ast_data, problem)

    def _build_prompt(
        self,
        code: str,
        ast_data: Dict,
        problem: Dict | None,
    ) -> str:
        """Xay dung prompt. Rubric lay tu ngan hang bai tap (neu co)."""

        features = ast_data.get("features", {})
        ast_summary = (
            f"Algorithms: {ast_data.get('algorithms', 'N/A')} | "
            f"Complexity: {ast_data.get('complexity', 0)} | "
            f"Loops: {features.get('loops', 0)} | "
            f"Recursion: {features.get('recursion', False)} | "
            f"Classes: {features.get('class_defined', False)} | "
            f"Functions: {features.get('func_count', 0)}"
        )

        # Rubric dong tu ngan hang bai tap
        if problem and problem.get("rubric"):
            rubric_section = f"""TIEU CHI CHAM (tu ngan hang bai tap):
{problem['rubric']}"""
        elif problem and problem.get("requirements"):
            rubric_section = f"""YEU CAU BAI TAP:
{problem['requirements']}

TIEU CHI CHAM: Chua co rubric cu the tu ngan hang bai tap.
Hay danh gia tong quat dua tren: do chinh xac cua logic, chat luong thuat toan,
phong cach code, va kha nang toi uu."""
        else:
            rubric_section = """LUU Y: Chua ket noi voi ngan hang bai tap nen KHONG CO tieu chi cham cu the.
Hay danh gia code dua tren:
- Logic co dung khong?
- Thuat toan co phu hop voi bai toan DSA khong?
- Code co sach se, de doc khong?
- Co toi uu khong?
KHONG cho diem cu the. Chi nhan xet va goi y."""

        return f"""BAN LA FULLSTACK DEVELOPER 10 NAM KINH NGHIEM dang review code DSA cua sinh vien.
Ban da lam viec tai Google, Grab va nhieu startup. Ban cham diem NGHIEM KHAC nhu dang review Pull Request that.

PHONG CACH CUA BAN:
- Noi thang, khong vong vo. Code te thi noi te.
- Luon hoi: "Neu day la production code, ban co merge PR nay khong?" — Neu khong thi khong xung dang diem cao.
- KHONG thuong hai. Code chay duoc KHONG co nghia la code tot. Junior nao cung viet code chay duoc.
- Ban de y den: naming conventions, code readability, edge cases, Big-O, va co phai code "smart" hay chi la code "chay duoc".

QUY TAC TRU DIEM:
- Code chay nhung logic sai = tru 15-20 diem.
- Khong xu ly edge cases (mang rong, null, so am, duplicate) = tru 5-10 diem MOI truong hop.
- Hardcode ket qua = 0 diem. KHONG THUONG LUONG.
- Brute-force O(n^2) khi co giai phap O(n log n) hoac O(n) = tru 15-20 diem.
- Bien dat ten "a", "b", "x", "temp", "data1" = tru 3-5 diem. Day KHONG phai code thi dau.
- Khong comment, khong docstring = tru 3 diem. Dev that LUON ghi chu.
- Code copy-paste lap lai = tru 5 diem. DRY principle.
- Import thua, code chet, print debug con sot = tru 2-3 diem.

THANG DIEM (NGHIEM KHAC):
- 90-100: XUAT SAC. Chi 5% bai dat duoc. Logic hoan hao, Big-O toi uu, code sach nhu production.
- 75-89: KHA. Y tuong dung, thuat toan phu hop, nhung con cho de cai thien.
- 60-74: TRUNG BINH. Chay duoc nhung code con "junior", nhieu cho chua tot.
- 40-59: YEU. Nhieu loi logic, thuat toan khong phu hop, code kho doc.
- 0-39: KHONG DAT. Sai co ban, khong hieu bai, hoac hardcode.

{rubric_section}

KET QUA PHAN TICH TU DONG:
{ast_summary}

MA NGUON CAN DANH GIA:
```python
{code}
```

REVIEW CODE NHU DANG DOC PULL REQUEST. Neu ban KHONG merge PR nay thi diem KHONG duoc cao.

TRA LOI BANG JSON (KHONG markdown, KHONG text them):
{{
  "has_rubric": {"true" if (problem and (problem.get("rubric") or problem.get("requirements"))) else "false"},
  "total_score": <0-100 neu co rubric, null neu khong co. NHO: 80+ chi cho code PRODUCTION-READY>,
  "breakdown": {{
    "logic_score": <0-40. Sai logic = max 15. Thieu edge cases = max 30. Hoan hao = 35-40>,
    "algorithm_score": <0-40. Brute-force = max 20. Dung nhung chua toi uu = max 30>,
    "style_score": <0-10. Khong comment = max 5. Ten bien xau = max 6. PEP8 chuan = 9-10>,
    "optimization_score": <0-10. Code thua = max 5. Clean va toi uu = 8-10>
  }},
  "detected_algo": "<Ten thuat toan phat hien. Vi du: Binary Search, BFS, Merge Sort>",
  "strengths": "<Chi khen nhung gi XUNG DANG. Viet ngan gon kieu dev: 'Logic xu ly edge case tot', 'Big-O toi uu'. 2-3 diem>",
  "weaknesses": "<Phe binh thang nhu code review: 'Dong 15: bien `x` khong ro nghia', 'Thieu xu ly mang rong'. 2-4 diem>",
  "reasoning_feedback": "<Review 5-7 cau. Viet nhu senior dev dang comment tren PR: chi ro loi cu the, dong nao, tai sao sai, Big-O that su la bao nhieu. Nghiem khac nhung CONG BANG — code tot thi cong nhan.>",
  "improvement_feedback": "<Goi y cu the kieu mentor: 'Thay vi dung 2 vong for long nhau O(n^2), hay dung HashMap de giam xuong O(n). Vi du: ...' Dang danh sach, uu tien loi nghiem trong nhat.>",
  "complexity_analysis": "<Time: O(?), Space: O(?). Giai thich tai sao — khong chi noi ket qua. Neu co cach tot hon thi de xuat.>"
}}"""

    def _parse_ai_response(
        self, raw_text: str, ast_data: Dict, problem: Dict | None
    ) -> Dict[str, Any]:
        try:
            clean = raw_text.strip()
            if clean.startswith("```"):
                clean = re.sub(r"^```(json)?\s*", "", clean)
                clean = re.sub(r"\s*```$", "", clean)
                clean = clean.strip()

            data = json.loads(clean)
            has_rubric = data.get("has_rubric", False)

            # Neu khong co rubric -> khong cho diem
            if not has_rubric or data.get("total_score") is None:
                return {
                    "total_score": None,
                    "breakdown": None,
                    "has_rubric": False,
                    "algorithms": data.get("detected_algo", ast_data.get("algorithms", "N/A")),
                    "strengths": data.get("strengths", ""),
                    "weaknesses": data.get("weaknesses", ""),
                    "reasoning": data.get("reasoning_feedback", "Khong co nhan xet."),
                    "improvement": data.get("improvement_feedback", "Khong co goi y."),
                    "complexity_analysis": data.get("complexity_analysis", ""),
                    "notes": [],
                    "ai_scored": True,
                }

            # Co rubric -> cho diem
            total = self._clamp(data.get("total_score", 0), 0, 100)
            breakdown = data.get("breakdown", {})

            return {
                "total_score": total,
                "breakdown": {
                    "logic_score": self._clamp(breakdown.get("logic_score", 0), 0, 40),
                    "algorithm_score": self._clamp(breakdown.get("algorithm_score", 0), 0, 40),
                    "style_score": self._clamp(breakdown.get("style_score", 0), 0, 10),
                    "optimization_score": self._clamp(breakdown.get("optimization_score", 0), 0, 10),
                },
                "has_rubric": True,
                "algorithms": data.get("detected_algo", ast_data.get("algorithms", "N/A")),
                "strengths": data.get("strengths", ""),
                "weaknesses": data.get("weaknesses", ""),
                "reasoning": data.get("reasoning_feedback", ""),
                "improvement": data.get("improvement_feedback", ""),
                "complexity_analysis": data.get("complexity_analysis", ""),
                "notes": [],
                "ai_scored": True,
            }

        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.error("Failed to parse AI JSON: %s | Raw: %s", exc, raw_text[:200])
            return self._use_fallback(ast_data, problem)

    # ═══════════════════════════════════════════
    #  Fallback (khi AI khong kha dung)
    # ═══════════════════════════════════════════

    def _use_fallback(self, ast_data: Dict, problem: Dict | None) -> Dict[str, Any]:
        has_rubric = bool(problem and (problem.get("rubric") or problem.get("requirements")))

        if has_rubric:
            fallback = ast_data.get("fallback_score", {})
            total = fallback.get("total_score", 30)
            breakdown = fallback.get("breakdown", {})
        else:
            total = None
            breakdown = None

        return {
            "total_score": total,
            "breakdown": breakdown,
            "has_rubric": has_rubric,
            "algorithms": ast_data.get("algorithms", "Basic Logic"),
            "strengths": "",
            "weaknesses": "",
            "reasoning": "Danh gia dua tren phan tich cau truc code (AST)." if has_rubric
                         else "Chua ket noi voi ngan hang bai tap. He thong chi phan tich cau truc code, khong cho diem.",
            "improvement": "",
            "complexity_analysis": "",
            "notes": [] if has_rubric else ["He thong chua cap nhat tieu chi."],
            "ai_scored": False,
        }

    # ═══════════════════════════════════════════
    #  Merge Results
    # ═══════════════════════════════════════════

    def _merge_results(
        self, ast_data: Dict, ai_data: Dict, problem: Dict | None
    ) -> Dict[str, Any]:
        has_rubric = ai_data.get("has_rubric", False)
        total = ai_data.get("total_score")

        if total is not None and has_rubric:
            status = "PASS" if total >= PASS_SCORE_THRESHOLD else "FAIL"
        else:
            status = "PENDING"

        merged_notes = ast_data.get("notes", []) + ai_data.get("notes", [])

        return {
            "filename": ast_data["filename"],
            "total_score": total,
            "breakdown": ai_data.get("breakdown"),
            "has_rubric": has_rubric,
            "status": status,
            "algorithms": ai_data.get("algorithms", ast_data.get("algorithms", "N/A")),
            "complexity": ast_data.get("complexity", 0),
            "max_loop_depth": ast_data.get("max_loop_depth", 0),
            "runtime": ast_data.get("runtime", "N/A"),
            "strengths": ai_data.get("strengths", ""),
            "weaknesses": ai_data.get("weaknesses", ""),
            "reasoning": ai_data.get("reasoning", ""),
            "improvement": ai_data.get("improvement", ""),
            "complexity_analysis": ai_data.get("complexity_analysis", ""),
            "notes": merged_notes,
            "valid_score": True,
            "ai_scored": ai_data.get("ai_scored", False),
            "fingerprint": ast_data.get("fingerprint"),
        }

    # ═══════════════════════════════════════════
    #  Utilities
    # ═══════════════════════════════════════════

    @staticmethod
    def _clamp(value: Any, min_val: int, max_val: int) -> int:
        try:
            return max(min_val, min(int(value), max_val))
        except (TypeError, ValueError):
            return min_val
