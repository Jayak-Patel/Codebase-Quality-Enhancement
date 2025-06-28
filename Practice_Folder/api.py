import requests

from google import genai
import subprocess
import os
file_path = os.path.join("..", "..")
# file = open(file_path, "r")


url = "https://sonarcloud.io/api/issues/search" # Replace with the actual API endpoint
header = {"Authorization": "Bearer 3afc5fe36e9a81f9760724c63ba552bd6e420f82"}
parameters = {"componentKeys" :"Jayak-Patel_spring-integration-samples", "files" : "applications/file-split-ftp/src/main/resources/application.properties"}
response = requests.get(url, headers=header, params = parameters)
# curl --request GET \}
#   --url 'https://sonarcloud.io/api/measures/component?metricKeys=ncloc%2Ccode_smells%2Ccomplexity&component=my_project_key' \
#   --header 'Authorization: Bearer my_token' 

# 3afc5fe36e9a81f9760724c63ba552bd6e420f82
client = genai.Client(api_key="AIzaSyAigsYXpwyvIixD3vMj4suedyh6E02NJGI")
chat = client.chats.create(model = "gemini-2.0-flash")



if response.status_code == 200:
    data = response.json() # If the response is in JSON format
    # Process the data
    counter = 0
    for issue in data.get('issues', []):
        print(f"Issue: {issue['message']}")
        print(f"Severity: {issue['severity']}")
        print(f"Type: {issue['type']}")
        print(f"Rule: {issue['rule']}")
        print(f"Line: {issue.get('line', 'N/A')}")
        print("—" * 30)
        if(True):
            file_path +='/spring-integration-samples/' + issue['component'][39:]
            print(file_path)
            with open(file_path, "r") as input:
                input_text = input.read()
            response = chat.send_message(
                issue['message'] + ". Here is an issue with some code. Write changes that can be made to the code to fix it. " + 
                "Please write the entire code file with all of its changes as a response." + "Do not add any description to this, only the code." +
                "If there is any comments in the code, do not remove them."+                 
                input_text
            )

            code = response.text[8:-3]
            result_path = file_path
            json_path = "testFolder/jsonResults.txt"
            with open(result_path, "w") as file:
                file.write(code)
            print(issue)               
            #important things to note: key of the issue, rule that it breaks, component(where it is located in), line(may not be necessary), 
            counter+=1
            file_path = os.path.join("..", "..")
        

else:
    print(f"Error: {response.status_code}")
    
 