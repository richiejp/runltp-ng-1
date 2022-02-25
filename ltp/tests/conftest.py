"""
Generic tests configuration
"""
import os
import stat
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "ssh_password_only: mark test to use SSH password-only server"
    )


@pytest.fixture
def prepare_tmpdir(tmpdir):
    """
    Prepare the temporary directory with LTP folders and tests.
    """
    os.environ["LTPROOT"] = str(tmpdir)
    os.environ["TMPDIR"] = str(tmpdir)

    # create testcases folder
    testcases = tmpdir.mkdir("testcases").mkdir("bin")

    script_sh = testcases.join("script.sh")
    script_sh.write(
        '#!/bin/bash\n'
        'echo ""\n'
        'echo ""\n'
        'echo "Summary:"\n'
        'echo "passed   $1"\n'
        'echo "failed   $2"\n'
        'echo "broken   $3"\n'
        'echo "skipped  $4"\n'
        'echo "warnings $5"\n'
    )

    st = os.stat(str(script_sh))
    os.chmod(str(script_sh), st.st_mode | stat.S_IEXEC)

    # create runtest folder
    root = tmpdir.mkdir("runtest")

    suitefile = root.join("dirsuite0")
    suitefile.write("dir01 script.sh 1 0 0 0 0")

    suitefile = root.join("dirsuite1")
    suitefile.write("dir01 script.sh 0 1 0 0 0")

    suitefile = root.join("dirsuite2")
    suitefile.write("dir01 script.sh 0 0 0 1 0")

    suitefile = root.join("dirsuite3")
    suitefile.write("dir01 script.sh 0 0 1 0 0")

    suitefile = root.join("dirsuite4")
    suitefile.write("dir01 script.sh 0 0 0 0 1")

    # create scenario_groups folder
    scenario_dir = tmpdir.mkdir("scenario_groups")

    scenario_def = scenario_dir.join("default")
    scenario_def.write("dirsuite0\ndirsuite1")

    scenario_def = scenario_dir.join("network")
    scenario_def.write("dirsuite2\ndirsuite3\ndirsuite4\ndirsuite5")
