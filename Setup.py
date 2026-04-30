https://git-scm.com/download/win

git --version


Step 1 — Initialize git
git init

Step 2 — Add the remote repo
git remote add origin https://github.com/michaelgwelch/metasys-chat.git

Step 3 — Pull the main branch
git pull origin main

Step 4 — Create and switch to your branch
git checkout -b meet/metasys-assistant

Step 5 — Stage all files
git add .

Step 6 — Commit
git commit -m "feat: metasys-assistant Milestone 1 and Milestone 2"

Step 7 — Push your branch
git push -u origin meet/metasys-assistant


powershellNew-Item .gitignore -ItemType File
Then open it in VSCode and paste this content:
.venv/
data/chroma_db/
__pycache__/
*.pyc
.env
Save the file, then run:
powershellgit rm -r --cached .venv
git rm -r --cached data/chroma_db
git add .gitignore
git commit -m "fix: add .gitignore and remove large folders from tracking"
git push origin meet/metasys-assistant --force



.venv/
data/chroma_db/
__pycache__/
*.pyc
.env
Now the real issue is that .venv and data/chroma_db were already committed in a previous commit, so even after adding .gitignore they are still tracked. Run these commands:
powershellgit rm -r --cached .venv
If that still throws an error, try with quotes:
powershellgit rm -r --cached ".venv"
git rm -r --cached "data/chroma_db"
git rm -r --cached "backend/__pycache__"
Then commit and force push:
powershellgit add .
git commit -m "fix: remove large folders from tracking"
git push origin meet/metasys-assistant --force
