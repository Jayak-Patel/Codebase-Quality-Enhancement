
from google import genai
import subprocess
import os
file_path = os.path.join("..", "..", "sonarqube", "server", "sonar-main", "src", "main", "java", "org", "sonar", "application", "process", "EsManagedProcess.java")
file = open(file_path, "r")
code = file.read()

print(code)


client = genai.Client(
  api_key="AIzaSyAigsYXpwyvIixD3vMj4suedyh6E02NJGI"
)

completion = client.models.generate_content(
  model="gemini-2.0-flash",
  contents= str(code) + ". Here is some code that has been written in java. Please make this code look more professional."

)

text = completion.text
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
      cmd = '/path/to/javac/javac ' + file_path 
      proc = subprocess.Popen(cmd, shell=True)

  except Exception as e:
      print(f"Error: {e}")
  else:
      print("Code seemed to work without any issues.")
