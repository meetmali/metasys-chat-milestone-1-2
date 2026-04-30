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


Step 1 — Delete the entire git history
Remove-Item -Recurse -Force .git

Step 2 — Start fresh
git init
git checkout -b meet/metasys-assistant

Step 3 — Add the remote
git remote add origin https://github.com/michaelgwelch/metasys-chat.git

Step 4 — Stage everything (the .gitignore will now exclude .venv and chroma_db)
git add .

Step 5 — Commit
git commit -m "feat: metasys-assistant Milestone 1 and Milestone 2"

Step 6 — Push
git push -u origin meet/metasys-assistant --force
