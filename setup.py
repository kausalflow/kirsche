import os

from setuptools import find_packages as _find_packages
from setuptools import setup as _setup

from kirsche.version import __version__

# read the contents of your README file
__CWD__ = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(__CWD__, "README.md"), encoding="utf-8") as fp:
    PACKAGE_LONG_DESCRIPTION = fp.read()

PACKAGE_NAME = "kirsche"
PACKAGE_VERSION = __version__
PACKAGE_DESCRIPTION = "Kirsche, connecting your papers."
PACKAGE_LONG_DESCRIPTION = PACKAGE_LONG_DESCRIPTION
PACKAGE_URL = "https://github.com/kausalflow/kirsche"


def _requirements():
    return [r for r in open("requirements.txt")]


def get_extra_requires(path, add_all=True):
    """
    get_extra_requires retrieves the extras requirements.
    Reference:
    https://hanxiao.io/2019/11/07/A-Better-Practice-for-Managing-extras-require-Dependencies-in-Python/
    :param path: path to the extras require specification
    :type path: str
    :param add_all: whether to include the keyword all, defaults to True
    :type add_all: bool, optional
    :return: The mapping of all the dependencies by extras keyword
    :rtype: dict
    """
    import re
    from collections import defaultdict

    with open(path) as fp:
        extra_deps = defaultdict(set)
        for k in fp:
            if k.strip() and not k.startswith("#"):
                tags = set()
                if ":" in k:
                    k, v = k.split(":")
                    tags.update(vv.strip() for vv in v.split(","))
                tags.add(re.split("[<=>]", k)[0])
                for t in tags:
                    extra_deps[t].add(k)

        # add tag `all` at the end
        if add_all:
            extra_deps["all"] = set(vv for v in extra_deps.values() for vv in v)

    return extra_deps


def setup():
    _setup(
        name=PACKAGE_NAME,
        version=PACKAGE_VERSION,
        description=PACKAGE_DESCRIPTION,
        long_description=PACKAGE_LONG_DESCRIPTION,
        long_description_content_type="text/markdown",
        url=PACKAGE_URL,
        author="L Ma",
        author_email="hi@leima.is",
        license="MIT",
        packages=_find_packages(exclude=("tests",)),
        install_requires=_requirements(),
        include_package_data=True,
        test_suite="nose.collector",
        tests_require=["nose"],
        extras_require=get_extra_requires("requirements.extras.txt"),
        entry_points={"console_scripts": ["kirsche=kirsche.command:kirsche"]},
        zip_safe=False,
    )


if __name__ == "__main__":
    setup()
    print(_find_packages(exclude=("tests",)))
