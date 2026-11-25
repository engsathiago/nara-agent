"""Installation behavior for index rows whose GitHub path was deferred at build time."""

from unittest.mock import MagicMock

from tools.skills_hub_github import GitHubAuth
from tools.skills_hub_models import SkillBundle
from tools.skills_hub_official import NaraIndexSource


def test_deferred_skills_sh_path_still_installs_from_repo_tree():
    identifier = "skills-sh/example/skills/useful-skill"
    src = NaraIndexSource(auth=GitHubAuth())
    src._index = {"skills": [{
        "name": "useful-skill", "description": "Example", "source": "skills.sh",
        "identifier": identifier, "repo": "example/skills", "path": "useful-skill",
        "trust_level": "community", "tags": [],
    }]}
    src._loaded = True
    bundle = SkillBundle(name="skills", files={"SKILL.md": "content"},
                         source="github", identifier="example/skills/skills/useful-skill",
                         trust_level="community")
    github = MagicMock()
    github.fetch.side_effect = [None, bundle]
    github._find_skill_in_repo_tree.return_value = "example/skills/skills/useful-skill"
    src._github = github

    installed = src.fetch(identifier)

    assert installed is bundle
    assert installed.name == "useful-skill"
    assert installed.source == "skills.sh"
    assert installed.identifier == identifier
    github._find_skill_in_repo_tree.assert_called_once_with("example/skills", "useful-skill")
