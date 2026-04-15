"""data-manager.py 单元测试

使用标准库 unittest + tempfile 进行测试。
每个测试用例在临时目录中操作，互不干扰。
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_PATH = os.path.join(PROJECT_ROOT, "scripts", "data-manager.py")
PYTHON = sys.executable


def run_cli(*args, cwd=None):
    """运行 data-manager.py CLI 并返回 (returncode, stdout, stderr)。"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [PYTHON, SCRIPT_PATH] + list(args),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=cwd or PROJECT_ROOT,
        env=env,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


class BaseTestCase(unittest.TestCase):
    """基类：每个测试用例使用独立的临时项目目录。"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="talent_test_")
        # 创建 data 子目录结构
        for subdir in ["data/jds", "data/candidates", "data/screens", "data/rules"]:
            os.makedirs(os.path.join(self.tmpdir, subdir), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def data_path(self, *parts):
        return os.path.join(self.tmpdir, *parts)

    def write_json(self, path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def read_json(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def cli_run(self, *args):
        """在临时目录中运行 CLI。"""
        return run_cli(*args, cwd=self.tmpdir)

    def create_test_jd_file(self, path, **overrides):
        data = {"company": "测试公司", "title": "高级工程师", **overrides}
        self.write_json(path, data)
        return path

    def create_test_candidate_file(self, path, **overrides):
        data = {"name": "张三", "current_company": "某公司", **overrides}
        self.write_json(path, data)
        return path


class TestJDCommands(BaseTestCase):
    """JD 命令测试。"""

    def test_jd_create_from_file(self):
        """从 JSON 文件创建 JD。"""
        f = self.create_test_jd_file(self.data_path("input.json"))
        rc, out, err = self.cli_run("jd", "create", f)
        self.assertEqual(rc, 0, f"stderr: {err}")
        # 验证文件已创建
        jds_dir = self.data_path("data", "jds")
        files = os.listdir(jds_dir)
        self.assertEqual(len(files), 1)
        jd = self.read_json(os.path.join(jds_dir, files[0]))
        self.assertEqual(jd["company"], "测试公司")
        self.assertEqual(jd["title"], "高级工程师")
        self.assertIn("id", jd)
        self.assertIn("created_at", jd)

    def test_jd_create_with_custom_id(self):
        """创建 JD 时使用自定义 ID。"""
        data = {"id": "jd-custom-001", "company": "A公司", "title": "CTO"}
        f = self.data_path("input.json")
        self.write_json(f, data)
        rc, out, err = self.cli_run("jd", "create", f)
        self.assertEqual(rc, 0, f"stderr: {err}")
        jd = self.read_json(self.data_path("data", "jds", "jd-custom-001.json"))
        self.assertEqual(jd["id"], "jd-custom-001")

    def test_jd_create_auto_id(self):
        """自动生成 JD ID。"""
        f = self.create_test_jd_file(self.data_path("input.json"))
        rc, out, err = self.cli_run("jd", "create", f)
        self.assertEqual(rc, 0, f"stderr: {err}")
        jds_dir = self.data_path("data", "jds")
        files = os.listdir(jds_dir)
        self.assertTrue(files[0].startswith("jd-"))

    def test_jd_list_empty(self):
        """空列表。"""
        rc, out, err = self.cli_run("jd", "list")
        self.assertEqual(rc, 0, f"stderr: {err}")
        # 空列表应返回空 JSON 数组
        data = json.loads(out)
        self.assertEqual(data, [])

    def test_jd_list(self):
        """列出多个 JD。"""
        for i in range(3):
            data = {"id": f"jd-{i:03d}", "company": f"公司{i}", "title": f"职位{i}"}
            f = self.data_path(f"input_{i}.json")
            self.write_json(f, data)
            self.cli_run("jd", "create", f)
        rc, out, err = self.cli_run("jd", "list")
        self.assertEqual(rc, 0, f"stderr: {err}")
        data = json.loads(out)
        self.assertEqual(len(data), 3)

    def test_jd_get(self):
        """获取单个 JD。"""
        data = {"id": "jd-001", "company": "B公司", "title": "CEO"}
        f = self.data_path("input.json")
        self.write_json(f, data)
        self.cli_run("jd", "create", f)
        rc, out, err = self.cli_run("jd", "get", "jd-001")
        self.assertEqual(rc, 0, f"stderr: {err}")
        jd = json.loads(out)
        self.assertEqual(jd["id"], "jd-001")
        self.assertEqual(jd["company"], "B公司")

    def test_jd_get_not_found(self):
        """获取不存在的 JD。"""
        rc, out, err = self.cli_run("jd", "get", "jd-nonexist")
        self.assertNotEqual(rc, 0)

    def test_jd_create_required_fields(self):
        """创建 JD 时自动填充 required fields。"""
        data = {"company": "C公司", "title": "VP"}
        f = self.data_path("input.json")
        self.write_json(f, data)
        rc, out, err = self.cli_run("jd", "create", f)
        self.assertEqual(rc, 0, f"stderr: {err}")
        jds_dir = self.data_path("data", "jds")
        files = os.listdir(jds_dir)
        jd = self.read_json(os.path.join(jds_dir, files[0]))
        # 必须有 id, company, title, created_at
        for field in ("id", "company", "title", "created_at"):
            self.assertIn(field, jd, f"Missing required field: {field}")


class TestCandidateCommands(BaseTestCase):
    """Candidate 命令测试。"""

    def test_candidate_create_from_file(self):
        """从 JSON 文件创建候选人。"""
        f = self.create_test_candidate_file(self.data_path("input.json"))
        rc, out, err = self.cli_run("candidate", "create", f)
        self.assertEqual(rc, 0, f"stderr: {err}")
        cand_dir = self.data_path("data", "candidates")
        files = os.listdir(cand_dir)
        self.assertEqual(len(files), 1)
        cand = self.read_json(os.path.join(cand_dir, files[0]))
        self.assertEqual(cand["name"], "张三")
        self.assertIn("id", cand)
        self.assertIn("created_at", cand)
        self.assertIn("updated_at", cand)

    def test_candidate_create_with_custom_id(self):
        """创建候选人时使用自定义 ID。"""
        data = {"id": "cand-99", "name": "李四"}
        f = self.data_path("input.json")
        self.write_json(f, data)
        rc, out, err = self.cli_run("candidate", "create", f)
        self.assertEqual(rc, 0, f"stderr: {err}")
        cand = self.read_json(self.data_path("data", "candidates", "cand-99.json"))
        self.assertEqual(cand["id"], "cand-99")

    def test_candidate_list_empty(self):
        """空列表。"""
        rc, out, err = self.cli_run("candidate", "list")
        self.assertEqual(rc, 0, f"stderr: {err}")
        data = json.loads(out)
        self.assertEqual(data, [])

    def test_candidate_list(self):
        """列出候选人。"""
        for i in range(3):
            data = {"id": f"cand-{i}", "name": f"候选人{i}"}
            f = self.data_path(f"input_{i}.json")
            self.write_json(f, data)
            self.cli_run("candidate", "create", f)
        rc, out, err = self.cli_run("candidate", "list")
        self.assertEqual(rc, 0, f"stderr: {err}")
        data = json.loads(out)
        self.assertEqual(len(data), 3)

    def test_candidate_list_filter_enrichment(self):
        """按 enrichment_level 过滤。"""
        # 创建不同 enrichment_level 的候选人
        for level in ["raw", "partial", "enriched"]:
            data = {"id": f"cand-{level}", "name": f"候选人{level}", "enrichment_level": level}
            f = self.data_path(f"input_{level}.json")
            self.write_json(f, data)
            self.cli_run("candidate", "create", f)

        # 过滤 enriched
        rc, out, err = self.cli_run("candidate", "list", "--enrichment", "enriched")
        self.assertEqual(rc, 0, f"stderr: {err}")
        data = json.loads(out)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["enrichment_level"], "enriched")

    def test_candidate_get(self):
        """获取单个候选人。"""
        data = {"id": "cand-42", "name": "王五"}
        f = self.data_path("input.json")
        self.write_json(f, data)
        self.cli_run("candidate", "create", f)
        rc, out, err = self.cli_run("candidate", "get", "cand-42")
        self.assertEqual(rc, 0, f"stderr: {err}")
        cand = json.loads(out)
        self.assertEqual(cand["id"], "cand-42")
        self.assertEqual(cand["name"], "王五")

    def test_candidate_get_not_found(self):
        """获取不存在的候选人。"""
        rc, out, err = self.cli_run("candidate", "get", "cand-nonexist")
        self.assertNotEqual(rc, 0)

    def test_candidate_update(self):
        """更新候选人信息。"""
        # 先创建
        data = {"id": "cand-1", "name": "赵六"}
        f = self.data_path("input.json")
        self.write_json(f, data)
        self.cli_run("candidate", "create", f)

        # 更新
        update_data = {"name": "赵六", "current_company": "新公司"}
        f2 = self.data_path("update.json")
        self.write_json(f2, update_data)
        rc, out, err = self.cli_run("candidate", "update", "cand-1", f2)
        self.assertEqual(rc, 0, f"stderr: {err}")

        # 验证
        cand = self.read_json(self.data_path("data", "candidates", "cand-1.json"))
        self.assertEqual(cand["name"], "赵六")
        self.assertEqual(cand["current_company"], "新公司")
        self.assertIn("updated_at", cand)

    def test_candidate_update_preserves_existing_fields(self):
        """更新时保留已有字段。"""
        data = {"id": "cand-2", "name": "孙七", "current_company": "旧公司", "phone": "123456"}
        f = self.data_path("input.json")
        self.write_json(f, data)
        self.cli_run("candidate", "create", f)

        update_data = {"current_company": "新公司"}
        f2 = self.data_path("update.json")
        self.write_json(f2, update_data)
        self.cli_run("candidate", "update", "cand-2", f2)

        cand = self.read_json(self.data_path("data", "candidates", "cand-2.json"))
        self.assertEqual(cand["current_company"], "新公司")
        self.assertEqual(cand["phone"], "123456")  # 保留
        self.assertEqual(cand["name"], "孙七")  # 保留

    def test_candidate_dedup_finds_duplicates(self):
        """dedup 找到同名同公司的候选人。"""
        for i in range(3):
            data = {
                "id": f"cand-dup-{i}",
                "name": "张三",
                "current_company": "某公司",
            }
            f = self.data_path(f"input_{i}.json")
            self.write_json(f, data)
            self.cli_run("candidate", "create", f)

        # 一个不同的人
        data = {"id": "cand-unique", "name": "李四", "current_company": "某公司"}
        f = self.data_path("input_unique.json")
        self.write_json(f, data)
        self.cli_run("candidate", "create", f)

        rc, out, err = self.cli_run("candidate", "dedup")
        self.assertEqual(rc, 0, f"stderr: {err}")
        result = json.loads(out)
        # 应该找到一组重复（3个同名同公司）
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]["candidates"]), 3)

    def test_candidate_dedup_no_duplicates(self):
        """dedup 无重复时返回空列表。"""
        for i in range(2):
            data = {"id": f"cand-{i}", "name": f"人{i}", "current_company": f"公司{i}"}
            f = self.data_path(f"input_{i}.json")
            self.write_json(f, data)
            self.cli_run("candidate", "create", f)

        rc, out, err = self.cli_run("candidate", "dedup")
        self.assertEqual(rc, 0, f"stderr: {err}")
        result = json.loads(out)
        self.assertEqual(result, [])

    def test_candidate_merge_sources(self):
        """merge 合并 sources 并提升 enrichment_level。"""
        # 创建候选人，带多个 sources
        data = {
            "id": "cand-merge-1",
            "name": "周八",
            "enrichment_level": "raw",
            "sources": [
                {"type": "linkedin", "url": "https://linkedin.com/in/zhouba"},
            ],
        }
        f = self.data_path("input.json")
        self.write_json(f, data)
        self.cli_run("candidate", "create", f)

        # 手动追加一个 source（模拟另一个来源的信息）
        cand_path = self.data_path("data", "candidates", "cand-merge-1.json")
        cand = self.read_json(cand_path)
        cand["sources"].append({"type": "boss", "url": "https://zhipin.com/u/zhouba"})
        cand["enrichment_level"] = "enriched"
        self.write_json(cand_path, cand)

        # merge
        rc, out, err = self.cli_run("candidate", "merge", "cand-merge-1")
        self.assertEqual(rc, 0, f"stderr: {err}")
        merged = json.loads(out)
        self.assertEqual(merged["enrichment_level"], "enriched")
        self.assertEqual(len(merged["sources"]), 2)

    def test_candidate_merge_not_found(self):
        """merge 不存在的候选人。"""
        rc, out, err = self.cli_run("candidate", "merge", "cand-nonexist")
        self.assertNotEqual(rc, 0)


class TestScreenCommands(BaseTestCase):
    """Screen 命令测试。"""

    def _create_jd(self, jd_id):
        data = {"id": jd_id, "company": "X公司", "title": "Dev"}
        f = self.data_path(f"jd_{jd_id}.json")
        self.write_json(f, data)
        self.cli_run("jd", "create", f)

    def _create_candidate(self, cand_id):
        data = {"id": cand_id, "name": "某人"}
        f = self.data_path(f"cand_{cand_id}.json")
        self.write_json(f, data)
        self.cli_run("candidate", "create", f)

    def test_screen_create(self):
        """创建 screening 结果。"""
        self._create_jd("jd-001")
        self._create_candidate("cand-001")
        rc, out, err = self.cli_run("screen", "create", "jd-001", "cand-001", "85")
        self.assertEqual(rc, 0, f"stderr: {err}")

        screen = self.read_json(
            self.data_path("data", "screens", "jd-001__cand-001.json")
        )
        self.assertEqual(screen["jd_id"], "jd-001")
        self.assertEqual(screen["candidate_id"], "cand-001")
        self.assertEqual(screen["score"], 85)
        self.assertIn("status", screen)
        self.assertIn("created_at", screen)

    def test_screen_list(self):
        """列出 JD 下的 screening 结果。"""
        self._create_jd("jd-001")
        for i in range(3):
            self._create_candidate(f"cand-{i}")
            self.cli_run("screen", "create", "jd-001", f"cand-{i}", str(80 + i))

        rc, out, err = self.cli_run("screen", "list", "jd-001")
        self.assertEqual(rc, 0, f"stderr: {err}")
        data = json.loads(out)
        self.assertEqual(len(data), 3)

    def test_screen_list_empty(self):
        """空 screening 列表。"""
        self._create_jd("jd-001")
        rc, out, err = self.cli_run("screen", "list", "jd-001")
        self.assertEqual(rc, 0, f"stderr: {err}")
        data = json.loads(out)
        self.assertEqual(data, [])

    def test_screen_update(self):
        """更新 screening 结果。"""
        self._create_jd("jd-001")
        self._create_candidate("cand-001")
        self.cli_run("screen", "create", "jd-001", "cand-001", "70")

        update_data = {"score": 90, "status": "passed", "notes": "面试优秀"}
        f = self.data_path("screen_update.json")
        self.write_json(f, update_data)
        rc, out, err = self.cli_run("screen", "update", "jd-001", "cand-001", f)
        self.assertEqual(rc, 0, f"stderr: {err}")

        screen = self.read_json(
            self.data_path("data", "screens", "jd-001__cand-001.json")
        )
        self.assertEqual(screen["score"], 90)
        self.assertEqual(screen["status"], "passed")
        self.assertEqual(screen["notes"], "面试优秀")


class TestRulesCommands(BaseTestCase):
    """Rules 命令测试。"""

    def test_rules_get_empty(self):
        """获取不存在客户端的偏好（返回空或默认值）。"""
        rc, out, err = self.cli_run("rules", "get", "client-a")
        self.assertEqual(rc, 0, f"stderr: {err}")

    def test_rules_get_after_add(self):
        """添加 correction 后获取。"""
        correction = json.dumps({"field": "education", "correction": "硕士"})
        rc, out, err = self.cli_run("rules", "add-correction", "client-a", correction)
        self.assertEqual(rc, 0, f"stderr: {err}")

        rc, out, err = self.cli_run("rules", "get", "client-a")
        self.assertEqual(rc, 0, f"stderr: {err}")
        data = json.loads(out)
        self.assertIn("corrections", data)
        self.assertEqual(len(data["corrections"]), 1)
        self.assertEqual(data["corrections"][0]["field"], "education")

    def test_rules_add_multiple_corrections(self):
        """多次添加 correction。"""
        for i in range(3):
            correction = json.dumps({"field": f"field{i}", "correction": f"修正{i}"})
            self.cli_run("rules", "add-correction", "client-b", correction)

        rc, out, err = self.cli_run("rules", "get", "client-b")
        self.assertEqual(rc, 0, f"stderr: {err}")
        data = json.loads(out)
        self.assertEqual(len(data["corrections"]), 3)


class TestValidateCommand(BaseTestCase):
    """Validate 命令测试。"""

    def test_validate_empty_data(self):
        """空数据通过验证。"""
        rc, out, err = self.cli_run("validate")
        self.assertEqual(rc, 0, f"stderr: {err}")

    def test_validate_valid_jd(self):
        """有效 JD 通过验证。"""
        data = {"id": "jd-valid", "company": "A", "title": "B"}
        f = self.data_path("input.json")
        self.write_json(f, data)
        self.cli_run("jd", "create", f)

        rc, out, err = self.cli_run("validate")
        self.assertEqual(rc, 0, f"stderr: {err}")

    def test_validate_missing_required_field(self):
        """缺失必需字段时验证失败。"""
        # 手动创建一个缺少 required field 的 JD
        bad_jd = {"id": "jd-bad", "company": "A"}  # 缺少 title
        self.write_json(self.data_path("data", "jds", "jd-bad.json"), bad_jd)

        rc, out, err = self.cli_run("validate")
        self.assertNotEqual(rc, 0, "Should fail with missing required field")

    def test_validate_invalid_enum(self):
        """无效枚举值时验证失败。"""
        # 创建一个 status 不合法的 candidate
        bad_cand = {
            "id": "cand-bad",
            "name": "X",
            "created_at": "2026-01-01",
            "updated_at": "2026-01-01",
            "status": "invalid_status",
        }
        self.write_json(
            self.data_path("data", "candidates", "cand-bad.json"), bad_cand
        )

        rc, out, err = self.cli_run("validate")
        self.assertNotEqual(rc, 0, "Should fail with invalid enum value")

    def test_validate_valid_candidate(self):
        """有效 candidate 通过验证。"""
        data = {"id": "cand-valid", "name": "有效候选人"}
        f = self.data_path("input.json")
        self.write_json(f, data)
        self.cli_run("candidate", "create", f)

        rc, out, err = self.cli_run("validate")
        self.assertEqual(rc, 0, f"stderr: {err}")


class TestAtomicWrite(BaseTestCase):
    """原子写入测试。"""

    def test_no_tmp_files_left(self):
        """写入后不应残留 .tmp 文件。"""
        data = {"id": "jd-atomic", "company": "A", "title": "B"}
        f = self.data_path("input.json")
        self.write_json(f, data)
        self.cli_run("jd", "create", f)

        # 检查所有 .tmp 文件
        for root, dirs, files in os.walk(self.tmpdir):
            for fname in files:
                self.assertFalse(
                    fname.endswith(".tmp"), f"Found leftover .tmp file: {fname}"
                )


class TestAutoTimestamps(BaseTestCase):
    """自动时间戳测试。"""

    def test_jd_created_at_auto_set(self):
        """JD 自动设置 created_at。"""
        data = {"company": "A", "title": "B"}
        f = self.data_path("input.json")
        self.write_json(f, data)
        rc, out, err = self.cli_run("jd", "create", f)
        self.assertEqual(rc, 0, f"stderr: {err}")

        jds_dir = self.data_path("data", "jds")
        files = os.listdir(jds_dir)
        jd = self.read_json(os.path.join(jds_dir, files[0]))
        self.assertIn("created_at", jd)
        # 应该是 ISO 日期格式
        self.assertRegex(jd["created_at"], r"\d{4}-\d{2}-\d{2}")

    def test_candidate_timestamps_auto_set(self):
        """候选人自动设置 created_at 和 updated_at。"""
        data = {"name": "X"}
        f = self.data_path("input.json")
        self.write_json(f, data)
        rc, out, err = self.cli_run("candidate", "create", f)
        self.assertEqual(rc, 0, f"stderr: {err}")

        cand_dir = self.data_path("data", "candidates")
        files = os.listdir(cand_dir)
        cand = self.read_json(os.path.join(cand_dir, files[0]))
        self.assertIn("created_at", cand)
        self.assertIn("updated_at", cand)
        self.assertRegex(cand["created_at"], r"\d{4}-\d{2}-\d{2}")
        self.assertRegex(cand["updated_at"], r"\d{4}-\d{2}-\d{2}")


class TestEdgeCases(BaseTestCase):
    """边界情况测试。"""

    def test_create_jd_nonexistent_file(self):
        """从不存在的文件创建 JD 应失败。"""
        rc, out, err = self.cli_run("jd", "create", "/nonexistent/file.json")
        self.assertNotEqual(rc, 0)

    def test_create_candidate_nonexistent_file(self):
        """从不存在的文件创建候选人应失败。"""
        rc, out, err = self.cli_run("candidate", "create", "/nonexistent/file.json")
        self.assertNotEqual(rc, 0)

    def test_create_duplicate_jd(self):
        """创建重复 ID 的 JD 应失败。"""
        data = {"id": "jd-dup", "company": "A", "title": "B"}
        f = self.data_path("input.json")
        self.write_json(f, data)
        self.cli_run("jd", "create", f)
        # 再次创建
        rc, out, err = self.cli_run("jd", "create", f)
        self.assertNotEqual(rc, 0, "Should fail on duplicate JD ID")

    def test_create_duplicate_candidate(self):
        """创建重复 ID 的候选人应失败。"""
        data = {"id": "cand-dup", "name": "X"}
        f = self.data_path("input.json")
        self.write_json(f, data)
        self.cli_run("candidate", "create", f)
        # 再次创建
        rc, out, err = self.cli_run("candidate", "create", f)
        self.assertNotEqual(rc, 0, "Should fail on duplicate candidate ID")


if __name__ == "__main__":
    unittest.main()
