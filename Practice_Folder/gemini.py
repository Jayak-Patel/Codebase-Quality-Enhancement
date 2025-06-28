
from google import genai
import subprocess
import os
# file_path = os.path.join("..", "..", "sonarqube", "server", "sonar-main", "src", "main", "java", "org", "sonar", "application", "process", "EsManagedProcess.java")
# file = open(file_path, "r")
# code = file.read()

# print(code)

client = genai.Client(api_key="AIzaSyAigsYXpwyvIixD3vMj4suedyh6E02NJGI")    
chat = client.chats.create(model="gemini-2.0-flash")

response = chat.send_message("Remember this number 35. If I ask you for this remembered number, put down 35.")
print(response.text)
response = chat.send_message("What is the remembered number?")
print (response.text)

completion = client.models.generate_content(
  model="gemini-2.0-flash",
  contents=  ". Here is some code that has been written in java. Please make this code look more professional."

)

completion = client.models.generate_content(
  model="gemini-2.0-flash",
  contents= "Remember this number 35. If I ask you for this remembered number, put down 35."

)
print(completion.text)

completion = client.models.generate_content(
  model="gemini-2.0-flash",
  contents= "What is the remembered number?"

)
print(completion.text)


print(text)
groups = text.split("```") 
print(groups)  # Output: [Description, code, excess]
print(groups[1]) # Seems to have the type of language it is in, then the code.
language, groups[1] = groups[1].split(maxsplit=1)

if(language == "python"):

    file_path = "testFolder/pythonTest.py"

    with open(file_path, "w") as file:
        file.write(groups[1])

    print(f"String saved to {file_path}")
    try:
        from testFolder import pythonTest #Essentially runs the code that was just written.
    except Exception as e:
        print(f"Error: {e}")
    else:
        print("Code seemed to work without any issues.")
elif(language == "java"):
  file_path = "testFolder/javaTest.java"
  with open(file_path, "w") as file:
      file.write(groups[1])

  print(f"String saved to {file_path}")
  try:
      cmd = 'javac ' + file_path 
      proc = subprocess.Popen(cmd, shell=True)

  except Exception as e:
      print(f"Error: {e}")
  else:
      print("Code seemed to work without any issues.")
