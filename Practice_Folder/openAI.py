from openai import OpenAI

client = OpenAI(
  api_key="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"
)

completion = client.chat.completions.create(
  model="gpt-4o-mini",
  store=True,
  messages=[
    {"role": "user", "content": "write a haiku about ai"}
  ]
)

print(completion.choices[0].message)
