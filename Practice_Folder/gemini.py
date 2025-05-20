
from google import genai

client = genai.Client(
  api_key="AIzaSyAigsYXpwyvIixD3vMj4suedyh6E02NJGI"
)

completion = client.models.generate_content(
  model="gemini-2.0-flash",
  contents="Please write short code that will print hello 5 times in python."

)

text = completion.text
groups = text.split("```") 
print(groups)  # Output: [Description, code, excess]
print(groups[1]) # Seems to have the type of language it is in, then the code.
language, groups[1] = groups[1].split(maxsplit=1)

if(language == "python"):

    file_path = "test.py" # Can be an absolute or relative path

    with open(file_path, "w") as file:
        file.write(groups[1])

    print(f"String saved to {file_path}")
    try:
        import test #Essentially runs the code that was just written.
    except Exception as e:
        print(f"Error: {e}")
    else:
        print("Code seemed to work without any issues.")

print(completion.text)

