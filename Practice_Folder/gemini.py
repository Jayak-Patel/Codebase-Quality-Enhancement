
from google import genai

client = genai.Client(
  api_key="AIzaSyAigsYXpwyvIixD3vMj4suedyh6E02NJGI"
)

completion = client.models.generate_content(
  model="gemini-2.0-flash",
  contents="Please write short code that take in a string and output the reverse of that string in python."

)

text = completion.text
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
      from testFolder import javaTest #Essentially runs the code that was just written.
  except Exception as e:
      print(f"Error: {e}")
  else:
      print("Code seemed to work without any issues.")
