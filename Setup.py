config.py
python# Author: Meet Mali
# Date: 30 April 2026
# Description: Stores all the settings for the project in one place.
#              Any value that can be changed, like server URLs or model
#              names, is defined here so it only needs to be updated once.

ingest.py
python# Author: Meet Mali
# Date: 30 April 2026
# Description: Reads the Metasys API documentation file and prepares it
#              for the chatbot to use. Breaks the content into smaller
#              pieces, processes them, and saves everything locally so
#              the chatbot can search through it when answering questions.
#              Run this once before starting the chatbot.

rag.py
python# Author: Meet Mali
# Date: 30 April 2026
# Description: Handles the question and answer flow for Milestone 1.
#              When a user asks a question, this file finds the most
#              relevant pieces of API documentation and passes them to
#              the language model to generate a response.

ingest_spaces.py
python# Author: Meet Mali
# Date: 30 April 2026
# Description: Connects to the MRAM server and pulls in all the building
#              space data. Fetches detailed information for each space
#              including its name, size, location, and equipment, then
#              saves everything locally so the chatbot can answer
#              questions about the building. Requires MRAM to be running.

rag_spaces.py
python# Author: Meet Mali
# Date: 30 April 2026
# Description: Handles the question and answer flow for Milestone 2.
#              When a user asks about building spaces, this file searches
#              through the saved space data and passes the most relevant
#              results to the language model to generate a response.

main.py
python# Author: Meet Mali
# Date: 30 April 2026
# Description: The main entry point for the application. Starts the web
#              server, serves the chat interface, and connects all the
#              routes for both Milestone 1 and Milestone 2 so the
#              chatbot is accessible from the browser.

index.html
<!--
  Author: Meet Mali
  Date: 30 April 2026
  Description: The chat interface that opens in the browser. Has a dark
               theme with a toggle to switch between asking questions
               about the API documentation and asking questions about
               building spaces. Responses from the model stream in
               word by word as they are generated.
-->

openapi.json
json// Author: Meet Mali
// Date: 30 April 2026
// Description: The official Metasys REST API specification file. Contains
//              a full description of all available API endpoints and how
//              to use them. This file is the knowledge source for
//              Milestone 1.     

.env
# Author: Meet Mali
# Date: 30 April 2026
# Description: A local configuration file that holds environment specific
#              settings like server addresses and model names. This file
#              is not committed to GitHub as it may contain values that
#              differ between machines.

requirements.txt
# Author: Meet Mali
# Date: 30 April 2026
# Description: Lists all the Python packages needed to run the project.
#              Install everything in this file once using pip before
#              starting the application.

.gitignore
# Author: Meet Mali
# Date: 30 April 2026
# Description: Tells Git which files and folders to ignore when committing
#              to the repository. Keeps generated files, local settings,
#              and cached data out of version control.
