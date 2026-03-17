from openai import AsyncOpenAI
from config import AI_API_TOKEN

client = AsyncOpenAI(
    api_key = AI_API_TOKEN,
    base_url = "https://openrouter.ai/api/v1"
)

async def generate_response(user_request: str, ai_model: str, previous_messages: list = [], attached_files: list = []):
    '''
    Делает запрос к ИИ.
    '''
    has_pdf = False
    addition_to_input_text = []
    content = []
    input_text = {
        "type": "input_text", "text": user_request
    }

    if attached_files:
        for file_type, file in attached_files:
            if file_type in ["pdf", "img"]:
                if file_type == "pdf":
                    has_pdf = True
                content.append(file)
            if file_type == "str":
                addition_to_input_text.append(file)
        if addition_to_input_text:
            for text_doc in addition_to_input_text:
                input_text["text"] = input_text["text"] + "\n\n" + text_doc
    content.append(input_text)

    if not previous_messages:
        dialogue = [{"role": "user", "content": content}]
    else:
        dialogue = previous_messages + [{"role": "user", "content": content}]

    if has_pdf:
            extra_body = {
                "plugins": [
                    {
                        "id": "file-parser",
                        "pdf": {
                            "engine": "pdf-text"
                        }
                    }
                ]
            }
    else:
        extra_body = None

    response = await client.responses.create(
        model = ai_model,
        input = dialogue,
        extra_body = extra_body
    )
    return response, dialogue
