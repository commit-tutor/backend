import requests
import json

content = input()
url="https://openrouter.ai/api/v1/chat/completions"
apikey = "Bearer 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"

headers = {
    "Authorization": apikey
}

data_dict={
  "model": "tngtech/deepseek-r1t2-chimera:free", # 사용하고자 하는 모델 
  "messages": [
    {
      "role": "user",
      "content":content
    }
  ]
}
response = requests.post(
    url, headers=headers, json=data_dict
)
if response.status_code != 200:
    print(f"API 호출 실패 (HTTP {response.status_code}): {response.text}")
    exit()

response_data = response.json()
answer = response_data["choices"][0]["message"]["content"]
print(answer)