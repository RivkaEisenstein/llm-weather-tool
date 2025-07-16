import requests
import json
import os
import asyncio

api_key = ""
url = ""


# --- Headers for API requests ---
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# --- Tool Definition ---
tools_weather = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current temperature for provided coordinates in celsius.",
        "parameters": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number"},
                "longitude": {"type": "number"}
            },
            "required": ["latitude", "longitude"],
            "additionalProperties": False
        },
        "strict": True
    }
}]

# --- Placeholder for the get_weather function ---
def get_weather(latitude: float, longitude: float) -> str:
    print(f"Calling get_weather with latitude: {latitude}, longitude: {longitude}")
    if latitude == 32.0853 and longitude == 34.7818: # Tel Aviv
        return "The current temperature in Tel Aviv is 28 degrees Celsius with clear skies."
    elif latitude == 32.0307 and longitude == 34.8335: # Bnei Brak (from your trace)
        return "The current temperature in Bnei Brak is 27 degrees Celsius and sunny."
    elif latitude == 31.7683 and longitude == 35.2137: # Jerusalem
        return "The current temperature in Jerusalem is 25 degrees Celsius and partly cloudy."
    else:
        return f"Weather data for latitude {latitude}, longitude {longitude} is not available."

# --- The openai_chat_completion function ---
async def openai_chat_completion(message: str):
    messages = [{"role": "user", "content": message}]

    try:
        response = requests.post(url, headers=headers, json={
            "model": "gpt-4o-mini",
            "messages": messages,
            "tools": tools_weather,
            "tool_choice": "required"
        },verify= False)

        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred in first request: {http_err} - {response.text if 'response' in locals() else 'No response object'}")
        return None
    except requests.exceptions.ConnectionError as conn_err:
        print(f"Connection error occurred in first request: {conn_err}")
        return None
    except requests.exceptions.Timeout as timeout_err:
        print(f"Timeout error occurred in first request: {timeout_err}")
        return None
    except requests.exceptions.RequestException as req_err:
        print(f"An unexpected error occurred in first request: {req_err}")
        return None

    completion = response.json()

    tool_calls = completion.get('choices', [{}])[0].get('message', {}).get('tool_calls')

    if not tool_calls:
        print("Warning: tool_choice was 'required' but no tool_calls found in the first response.")
        return completion

    # **CRITICAL CHANGE HERE**: Append the assistant message with tool_calls directly
    # Ensure 'content' is present, even if None or an empty string, as required by the API.
    assistant_message_with_tool_calls = completion['choices'][0]['message']
    if 'content' not in assistant_message_with_tool_calls or assistant_message_with_tool_calls['content'] is None:
        assistant_message_with_tool_calls['content'] = "" # Ensure content is a string, even if empty

    messages.append(assistant_message_with_tool_calls)

    tool_call = tool_calls[0] # Assuming only one tool call

    # Execute the tool
    if tool_call['function']['name'] == "get_weather":
        try:
            args = json.loads(tool_call['function']['arguments'])
            latitude = args.get("latitude")
            longitude = args.get("longitude")

            if latitude is None or longitude is None:
                print("Error: latitude or longitude missing in tool arguments.")
                return None
            result = get_weather(latitude, longitude)
        except json.JSONDecodeError:
            print(f"Error decoding JSON for tool arguments: {tool_call['function']['arguments']}")
            return None
        except KeyError as e:
            print(f"Missing expected key in tool arguments: {e}")
            return None
    else:
        print(f"Unknown tool called: {tool_call['function']['name']}")
        return None

    # Append the tool result message
    messages.append({
        "role": "tool",
        "tool_call_id": tool_call['id'],
        "content": result # result is already a string from get_weather
    })

    try:
        response2 = requests.post(url, headers=headers, json={
            "model": "gpt-4o-mini",
            "messages": messages,
            "tools": tools_weather
        },verify = False)
        response2.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred in second request: {http_err} - {response2.text if 'response2' in locals() else 'No response2 object'}")
        return None
    except requests.exceptions.RequestException as req_err:
        print(f"An unexpected error occurred in second request: {req_err}")
        return None

    return response2.json()

# --- Main execution block ---
if __name__ == "__main__":
    query = "what is the weather in Tel aviv?"
    print(f"Query: {query}")

    llm_response = asyncio.run(openai_chat_completion(query))

    if llm_response:
        print("\nFull LLM response JSON:")
        print(json.dumps(llm_response, indent=2, ensure_ascii=False))

        if 'choices' in llm_response and llm_response['choices']:
            final_message_content = llm_response['choices'][0]['message'].get('content')
            if final_message_content:
                print("\nFinal message content from LLM:")
                print(final_message_content)
            else:
                print("LLM response did not contain final message content (content field was empty or missing).")
        else:
            print("No 'choices' found in the LLM response (unexpected structure).")
    else:
        print("Failed to get LLM response.")
