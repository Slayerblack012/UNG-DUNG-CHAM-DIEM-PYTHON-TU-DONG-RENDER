"""
DSA AutoGrader — Static Code Analyzer.

Phân tích mã nguồn Python qua AST (Abstract Syntax Tree):
  • Kiểm tra cú pháp & an toàn
  • Đo độ phức tạp (Cyclomatic Complexity)
  • Trích xuất đặc trưng thuật toán (Algorithm Feature Extraction)
  • Tạo AST Fingerprint cho phát hiện đạo văn
  • Chạy kiểm thử động (Dynamic Testing — sandbox)
"""

import ast
import os
import subprocess
import sys
import tempfile
import time
import logging
from typing import Any, Dict, List, Set

from app.core.config import DYNAMIC_TEST_TIMEOUT

logger = logging.getLogger("dsa.analyzer")

# ═══════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════
DANGEROUS_IMPORTS: Set[str] = {
    "os", "sys", "subprocess", "shutil", "socket",
    "requests", "pickle", "urllib", "ctypes",
}

DANGEROUS_FUNCTIONS: Set[str] = {
    "exec", "eval", "compile", "open", "__import__",
}


# ═══════════════════════════════════════════
#  AST Visitor — Feature Extraction
# ═══════════════════════════════════════════
class ComplexityVisitor(ast.NodeVisitor):
    """
    Duyệt AST để trích xuất đặc trưng code:
      - Cyclomatic complexity
      - Loop depth (nested loops)
      - Recursion detection
      - Data structure usage
      - Algorithm pattern hints
      - Function / Variable names (cho algo detection)
      - AST fingerprint nodes (cho plagiarism)
    """

    def __init__(self) -> None:
        self.complexity: int = 1
        self.max_loop_depth: int = 0
        self._current_loop_depth: int = 0
        self._current_func_name: str | None = None

        self.features: Dict[str, Any] = {
            "loops": 0,
            "ifs": 0,
            "nested_loops": False,
            "recursion": False,
            "class_defined": False,
            "func_count": 0,
            "imports": set(),
            "func_names": [],
            "var_names": [],
            "ds_usage": {
                "list": False,
                "dict": False,
                "set": False,
                "tuple": False,
                "deque": False,
            },
            "algo_hints": {
                "swap": False,
                "binary_search": False,
                "dp_memo": False,
                "matrix": False,
                "divide_conquer": False,
            },
            "fingerprint_nodes": [],
        }

    # ── Functions & Classes ────────────────────

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        prev_func = self._current_func_name
        self._current_func_name = node.name

        self.features["func_count"] += 1
        self.features["func_names"].append(node.name.lower())

        # Recursion: function gọi chính nó
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == node.name
            ):
                self.features["recursion"] = True

        self.generic_visit(node)
        self._current_func_name = prev_func

    visit_AsyncFunctionDef = visit_FunctionDef  # Xử lý async def tương tự

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.features["class_defined"] = True
        self.features["var_names"].append(node.name.lower())
        self.generic_visit(node)

    # ── Control Flow ───────────────────────────

    def visit_For(self, node: ast.For) -> None:
        self._enter_loop()
        self.complexity += 1
        self.generic_visit(node)
        self._exit_loop()

    def visit_While(self, node: ast.While) -> None:
        self._enter_loop()
        self.complexity += 1

        # Heuristic: Binary Search = While + chia đôi (// 2 hoặc >> 1)
        if any(self._is_halving_op(n) for n in ast.walk(node)):
            self.features["algo_hints"]["binary_search"] = True

        self.generic_visit(node)
        self._exit_loop()

    def visit_If(self, node: ast.If) -> None:
        self.features["ifs"] += 1
        self.complexity += 1
        self.generic_visit(node)

    # ── Imports ────────────────────────────────

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.features["imports"].add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self.features["imports"].add(node.module)
            # Detect deque, heapq, etc.
            if "collections" in node.module:
                self.features["ds_usage"]["deque"] = True
        self.generic_visit(node)

    # ── Assignments & Names ────────────────────

    def visit_Assign(self, node: ast.Assign) -> None:
        # Detect swap pattern:  a, b = b, a
        if (
            isinstance(node.targets[0], ast.Tuple)
            and len(node.targets[0].elts) == 2
            and isinstance(node.value, ast.Tuple)
        ):
            self.features["algo_hints"]["swap"] = True

        # DP / Memoization hints
        for target in node.targets:
            if isinstance(target, ast.Name):
                name_lower = target.id.lower()
                self.features["var_names"].append(name_lower)
                if any(kw in name_lower for kw in ("dp", "memo", "cache", "table")):
                    self.features["algo_hints"]["dp_memo"] = True

        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        """Thu thập tên biến sử dụng trong code."""
        if isinstance(node.ctx, (ast.Store, ast.Load)):
            self.features["var_names"].append(node.id.lower())
        self.generic_visit(node)

    # ── Data Structures ────────────────────────

    def visit_List(self, node: ast.List) -> None:
        self.features["ds_usage"]["list"] = True
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        self.features["ds_usage"]["dict"] = True
        self.generic_visit(node)

    def visit_Set(self, node: ast.Set) -> None:
        self.features["ds_usage"]["set"] = True
        self.generic_visit(node)

    def visit_Tuple(self, node: ast.Tuple) -> None:
        self.features["ds_usage"]["tuple"] = True
        self.generic_visit(node)

    # ── Subscript (Matrix Detection) ──────────

    def visit_Subscript(self, node: ast.Subscript) -> None:
        # arr[i][j] → 2D array access (Matrix)
        if isinstance(node.value, ast.Subscript):
            self.features["algo_hints"]["matrix"] = True
        self.generic_visit(node)

    # ── Call Detection ─────────────────────────

    def visit_Call(self, node: ast.Call) -> None:
        """Thu thập tên hàm được gọi."""
        if isinstance(node.func, ast.Name):
            self.features["var_names"].append(node.func.id.lower())
        elif isinstance(node.func, ast.Attribute):
            self.features["var_names"].append(node.func.attr.lower())
        self.generic_visit(node)

    # ── Internal Helpers ───────────────────────

    def _enter_loop(self) -> None:
        self.features["loops"] += 1
        self._current_loop_depth += 1
        self.max_loop_depth = max(self.max_loop_depth, self._current_loop_depth)
        if self._current_loop_depth > 1:
            self.features["nested_loops"] = True

    def _exit_loop(self) -> None:
        self._current_loop_depth -= 1

    @staticmethod
    def _is_halving_op(node: ast.AST) -> bool:
        """Kiểm tra phép chia đôi: x // 2  hoặc  x >> 1."""
        return (
            isinstance(node, ast.BinOp)
            and isinstance(node.op, (ast.FloorDiv, ast.RShift))
            and isinstance(node.right, ast.Constant)
            and node.right.value == 2
        )

    def generic_visit(self, node: ast.AST) -> None:
        """Ghi lại loại node cho fingerprinting."""
        if not isinstance(node, (ast.Load, ast.Store, ast.Del, ast.Module)):
            self.features["fingerprint_nodes"].append(type(node).__name__)
        super().generic_visit(node)


# ═══════════════════════════════════════════
#  Main Analyzer Service
# ═══════════════════════════════════════════
class ASTAnalyzer:
    """
    Service: Phân tích mã nguồn Python (Static Analysis).

    Pipeline:
      1. Syntax Validation
      2. Safety Check (dangerous imports/functions)
      3. Complexity & Feature Extraction (AST Visitor)
      4. Algorithm Detection (heuristic)
      5. Fingerprint Generation (plagiarism)
      6. Fallback Scoring (khi AI không khả dụng)
    """

    # ── Public API ─────────────────────────────

    def check_safety(self, tree: ast.AST) -> List[str]:
        """Quét các thư viện / hàm nguy hiểm trong code."""
        violations: List[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_module = alias.name.split(".")[0]
                    if root_module in DANGEROUS_IMPORTS:
                        violations.append(f"Import thư viện bị cấm: {alias.name}")

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_module = node.module.split(".")[0]
                    if root_module in DANGEROUS_IMPORTS:
                        violations.append(f"Import module bị cấm: {node.module}")

            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in DANGEROUS_FUNCTIONS:
                    violations.append(f"Hàm không an toàn: {node.func.id}()")

        return violations

    def analyze_code(
        self,
        code: str,
        filename: str,
        topic: str | None = None,
    ) -> Dict[str, Any]:
        """
        Phân tích toàn diện một file Python.

        Returns:
            Dict chứa kết quả phân tích, bao gồm:
              - valid_score, algorithms, complexity, features, fingerprint, notes
              - fallback_score (điểm dự phòng khi không có AI)
        """
        start = time.time()

        # Step 1: Parse AST
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return self._error_report(
                filename,
                f"Lỗi cú pháp tại dòng {exc.lineno}: {exc.msg}",
            )
        except Exception as exc:
            return self._error_report(filename, f"Lỗi phân tích: {exc}")

        # Step 2: Safety
        violations = self.check_safety(tree)
        if violations:
            return self._error_report(
                filename,
                "Vi phạm bảo mật",
                notes=violations,
                status="FLAG",
            )

        # Step 3: Extract Features
        visitor = ComplexityVisitor()
        visitor.visit(tree)

        # Step 4: Detect Algorithms
        detected_algos = self._detect_algorithms(visitor.features)

        # Step 5: Fingerprint (n-gram trên AST nodes)
        nodes = visitor.features["fingerprint_nodes"]
        fingerprint = []
        if len(nodes) >= 3:
            fingerprint_set = {"-".join(nodes[i : i + 3]) for i in range(len(nodes) - 2)}
            fingerprint = list(fingerprint_set)  # Ép kiểu List -> JSON Serializable

        # Step 6: Fallback Score
        fallback = self._calculate_fallback_score(visitor, detected_algos)

        runtime = f"{(time.time() - start) * 1000:.0f}ms"

        return {
            "filename": filename,
            "valid_score": True,
            "algorithms": ", ".join(detected_algos) if detected_algos else "Basic Logic",
            "complexity": visitor.complexity,
            "max_loop_depth": visitor.max_loop_depth,
            "runtime": runtime,
            "fingerprint": fingerprint,
            "fallback_score": fallback,
            "notes": [],
            "features": {
                k: v for k, v in visitor.features.items()
                if k != "fingerprint_nodes"  # Quá lớn, không cần expose
            },
        }

    def run_dynamic_test(
        self,
        code: str,
        test_input: str,
        expected_output: str | None = None,
        timeout: int = DYNAMIC_TEST_TIMEOUT,
    ) -> Dict[str, Any]:
        """
        Chạy code trong sandbox và so sánh output (nếu có expected).

        Returns:
            Dict: success, output, error, passed (nếu có expected_output)
        """
        temp_file = None
        try:
            # Preamble: Xóa bỏ các built-ins nguy hiểm ở Runtime để chống sandbox bypass
            secure_preamble = (
                "import builtins\n"
                "for risky in ['open', 'exec', 'eval', 'compile', '__import__']:\n"
                "    if hasattr(builtins, risky):\n"
                "        delattr(builtins, risky)\n"
                "del builtins\n\n"
            )
            secure_code = secure_preamble + code

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(secure_code)
                temp_file = tmp.name

            result = subprocess.run(
                [sys.executable, temp_file],
                input=test_input,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            actual = result.stdout.strip()
            response: Dict[str, Any] = {
                "success": result.returncode == 0,
                "output": actual,
                "error": result.stderr.strip(),
            }

            # So sánh output nếu có expected
            if expected_output is not None:
                response["passed"] = actual == expected_output.strip()

            return response

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Time Limit Exceeded", "passed": False}
        except Exception as exc:
            return {"success": False, "error": f"Runtime Error: {exc}", "passed": False}
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass

    # ── Private Helpers ────────────────────────

    def _detect_algorithms(self, features: Dict) -> List[str]:
        """
        Nhận diện thuật toán & CTDL qua đặc trưng AST.
        Kết hợp cả heuristic patterns + tên hàm/biến.
        """
        detected: List[str] = []
        hints = features.get("algo_hints", {})

        # 1. Pattern-based Detection
        if features.get("recursion"):
            detected.append("Recursion")
        if features.get("nested_loops"):
            detected.append("Nested Loops")
        elif features.get("loops", 0) > 0:
            detected.append("Iterative Logic")
        if hints.get("binary_search"):
            detected.append("Binary Search")
        if hints.get("dp_memo"):
            detected.append("Dynamic Programming")
        if hints.get("matrix"):
            detected.append("Matrix Operations")
        if hints.get("swap"):
            detected.append("Swap Pattern")

        # 2. Name-based Detection (từ tên hàm & biến)
        all_names = " ".join(
            features.get("func_names", []) + features.get("var_names", [])
        )

        name_mappings = {
            "binary_search": "Binary Search",
            "binarysearch": "Binary Search",
            "quick_sort": "Quick Sort",
            "quicksort": "Quick Sort",
            "merge_sort": "Merge Sort",
            "mergesort": "Merge Sort",
            "bubble_sort": "Bubble Sort",
            "bubblesort": "Bubble Sort",
            "insertion_sort": "Insertion Sort",
            "insertionsort": "Insertion Sort",
            "selection_sort": "Selection Sort",
            "selectionsort": "Selection Sort",
            "heap_sort": "Heap Sort",
            "heapsort": "Heap Sort",
            "factorial": "Math/Factorial",
            "fibonacci": "Dynamic Programming / Fibonacci",
            "dfs": "Depth-First Search",
            "bfs": "Breadth-First Search",
            "dijkstra": "Dijkstra's Algorithm",
            "linkedlist": "Linked List",
            "linked_list": "Linked List",
            "stack": "Stack",
            "queue": "Queue",
            "tree": "Tree Structure",
            "graph": "Graph Structure",
            "hash_map": "Hash Map",
            "hashmap": "Hash Map",
        }

        for keyword, label in name_mappings.items():
            if keyword in all_names and label not in detected:
                detected.append(label)

        # 3. Data Structure Detection qua operations
        if "append" in all_names and "pop" in all_names:
            if not any(x in detected for x in ("Stack", "Queue")):
                detected.append("Stack/Queue Operations")

        return sorted(set(detected))

    def _calculate_fallback_score(
        self,
        visitor: ComplexityVisitor,
        detected_algos: List[str],
    ) -> Dict[str, Any]:
        """
        Tính điểm dự phòng khi AI không khả dụng.
        Dựa trên phân tích AST features.

        Scoring breakdown:
          - Logic/Structure  (0–40)
          - Algorithm Usage   (0–40)
          - Code Style        (0–10)
          - Optimization      (0–10)
        """
        features = visitor.features

        # ── Logic & Structure (0-40) ──
        logic = 15  # Base: code chạy được, không lỗi syntax
        if features["func_count"] > 0:
            logic += 8   # Có tổ chức hàm
        if features["class_defined"]:
            logic += 5   # OOP
        if features["recursion"]:
            logic += 6   # Đệ quy
        if features["loops"] > 0:
            logic += 4   # Có vòng lặp
        if features["ifs"] > 0:
            logic += 2   # Có xử lý điều kiện
        logic = min(logic, 40)

        # ── Algorithm (0-40) ──
        algo = 10  # Base
        algo += min(len(detected_algos) * 8, 20)       # Mỗi thuật toán +8, tối đa +20
        algo += min(visitor.complexity - 1, 10)         # Complexity bonus, tối đa +10
        algo = min(algo, 40)

        # ── Code Style (0-10) ──
        style = 6   # Base: không đánh giá sâu PEP8 mà không có tool
        if features["func_count"] >= 2:
            style += 2  # Tổ chức code tốt
        if any(features["ds_usage"].values()):
            style += 2  # Sử dụng CTDL Python
        style = min(style, 10)

        # ── Optimization (0-10) ──
        optim = 5   # Base
        if not features["nested_loops"]:
            optim += 2  # Tránh nested loops
        if features["ds_usage"].get("set") or features["ds_usage"].get("dict"):
            optim += 2  # Dùng hash-based DS
        if features["algo_hints"].get("dp_memo"):
            optim += 1  # Memoization
        optim = min(optim, 10)

        total = logic + algo + style + optim

        return {
            "total_score": total,
            "breakdown": {
                "logic_score": logic,
                "algorithm_score": algo,
                "style_score": style,
                "optimization_score": optim,
            },
        }

    @staticmethod
    def _error_report(
        filename: str,
        message: str,
        notes: List[str] | None = None,
        status: str = "FAIL",
    ) -> Dict[str, Any]:
        """Tạo báo cáo lỗi chuẩn hóa."""
        return {
            "filename": filename,
            "valid_score": False,
            "total_score": 0,
            "status": status,
            "algorithms": "Phân tích thất bại",
            "complexity": 0,
            "runtime": "0ms",
            "breakdown": {},
            "notes": [message] + (notes or []),
        }
