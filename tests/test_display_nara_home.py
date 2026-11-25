"""display_nara_home() renders POSIX separators on every platform.

Maintainer catch (#95681 arc): on Windows with a custom NARA_HOME under
the user profile (e.g. AppData/Local/nara), ``"~/" +
str(home.relative_to(Path.home()))`` produced the mixed-separator chimera
``~/AppData\\Local\\nara`` — which then leaked into every consumer that
appends sub-paths (the skill_manage schema showed the agent
``~/AppData\\Local\\nara/skills/``). The ``~/`` shorthand implies POSIX
rendering; the whole string must be consistent.
"""
import os
import sys
import unittest
from pathlib import Path, PureWindowsPath
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestDisplayNaraHomePosix(unittest.TestCase):
    def test_nested_home_renders_forward_slashes(self):
        """Simulate the Windows shape portably: home nested several levels
        under the user profile must render with forward slashes only."""
        import nara_constants as hc

        fake_userhome = Path.home()
        nested = fake_userhome / "AppData" / "Local" / "nara"
        with patch.object(hc, "get_nara_home", return_value=nested):
            out = hc.display_nara_home()
        self.assertEqual(out, "~/AppData/Local/nara")
        self.assertNotIn("\\", out)

    def test_default_home_unchanged(self):
        import nara_constants as hc

        with patch.object(hc, "get_nara_home",
                          return_value=Path.home() / ".nara"):
            out = hc.display_nara_home()
        self.assertEqual(out, "~/.nara")

    def test_outside_home_falls_back_to_absolute(self):
        import nara_constants as hc

        outside = Path("/opt/nara-custom") if os.name != "nt" else Path("C:/opt/nara-custom")
        with patch.object(hc, "get_nara_home", return_value=outside):
            out = hc.display_nara_home()
        self.assertEqual(out, str(outside))

    def test_no_serving_schema_carries_tilde_backslash_chimera(self):
        """Fleet guard: no served tool schema string may combine '~/' with
        a backslash — the class of bug, not the one site."""
        from model_tools import get_tool_definitions

        offenders = []

        def walk(o, tool):
            if isinstance(o, str):
                if "~/" in o and "\\" in o:
                    offenders.append((tool, o[:80]))
            elif isinstance(o, dict):
                for v in o.values():
                    walk(v, tool)
            elif isinstance(o, list):
                for v in o:
                    walk(v, tool)

        for t in get_tool_definitions(quiet_mode=True):
            walk(t, t["function"]["name"])
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
