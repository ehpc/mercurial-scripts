# :dragon_face: mercurial-scripts

This repository is a collection of different scripts and hooks for Mercurial VCS.

## :baby_chick: clone-commits.py

This is a hook which clones any incoming revisions to other repositories.
For example, you have a remote repositories #1, #2, #3.
You can setup this hook so that if anyone pushes to #1, changesets will be automatically pushed to #2 and #3.
All repositories should reside inside the same filesystem.

## :zap: superlog.py

This is a hook which creates a detailed commit log and copies it to the clipboard for fast pasting anywhere you need.
