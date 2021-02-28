from setuptools import setup


setup(
    name="mpd-remote",
    version="0.2",
    description="Control MPD with a remote control.",
    python_requires=">=3.7.0",
    author="Ben Morgan",
    author_email="cassava@iexu.de",
    license="MIT",
    keywords=("mpd", "flirc", "denon", "remote", "music"),
    install_requires=[
        "appdirs",
        "click",
        "gtts",
        "python-mpd2",
        "readchar",
    ],
    packages=["mpd_remote"],
    package_dir={"": "."},
    package_data={},
    entry_points={"console_scripts": ["mpd-remote = mpd_remote.__main__:main"]},
)
