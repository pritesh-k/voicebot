import logging
from typing import Optional

import requests
from fastapi import FastAPI
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware


class ChatBot:
    def __init__(self, name):
        self.name = name
        self.logger = logging.getLogger("ChatBot")
        self.is_scheduling = False
        self.last_stage = ""
        self.do_repeat = False
        self.intent = ""
        self.response_data = {}
        self.url = "http://localhost:5005/model/parse"
        self.headers = {"Content-Type": "application/json"}

    def interact_with_rasa_nlu(self, user_input):
        data = {"text": user_input}
        response = requests.post(self.url, json=data, headers=self.headers)
        response_data_json = response.json()
        print("Rasa response_data:", response_data_json)

        return response_data_json

    def process_intent(self, request_data):
        response_data_api = {}
        if "reschedule" == self.intent:
            res = "Sure, please provide me your mobile number."
            print("Bot --> ", res)
            print(" reschedule -------------------------------------------")

            response_data_api = {"prevIntent": "reschedule", "res": res, "status_code": 200,
                                 "status_message": "CONTINUE"}

        elif "schedule" == self.intent:
            print(" schedule -------------------------------------------")
            prevIntent = request_data["prevIntent"]
            if prevIntent == "welcome":
                res = "Please select a date and month"
                response_data_api = {"prevIntent": "schedule", "res": res, "status_code": 200,
                                     "status_message": "CONTINUE"}
            else:
                res = "Unable to process the request, call us later"
                response_data_api = {"prevIntent": "schedule", "res": res, "status_code": 200,
                                     "status_message": "FINISH"}

        elif "appointmentDateMonth" == self.intent:

            entities = self.response_data.get("entities", [])

            found_date = None
            found_month = None

            for entity_info in entities:
                entity_type = entity_info["entity"]
                entity_value = entity_info["value"]

                if entity_type == "date":
                    print(f"Found date: {entity_value}")
                    found_date = entity_value

                elif entity_type == "month":
                    print(f"Found month: {entity_value}")
                    found_month = entity_value

            if found_date is None:
                # Your logic for handling dates in the schedule section
                print(f"Using date: {found_date}")
                res = "Sorry, I didn't catch the date. Can you please provide it again?"
                response_data_api = {"prevIntent": "appointmentDateMonth", "res": res, "status_code": 200,
                                     "status_message": "CONTINUE"}
                return response_data_api
            elif found_month is None:
                # Your logic for handling months in the schedule section
                print(f"Using month: {found_month}")
                res = "Sorry, I didn't catch the month. Can you please provide it again?"
                response_data_api = {"prevIntent": "appointmentDateMonth", "res": res, "status_code": 200,
                                     "status_message": "CONTINUE"}
                return response_data_api

            date_month = found_date + "/" + found_month
            api_url = f"http://localhost:8000/api/doctor-availability/available-time-slots?date={date_month}"
            response = requests.get(api_url)

            if response.status_code == 200:
                api_data = response.json()
                status_message = api_data.get("statusMessage")
                print(api_data)

                if status_message == "CONTINUE":
                    # Set the response_data based on the API data
                    available_slots = api_data.get('results', [])
                    if available_slots:
                        slots_message = ', '.join(str(slot.get('time', '')) for slot in available_slots)
                        res = f"I have the following availability {slots_message}. When would you like to come in?"
                        response_data_api = {"prevIntent": "appointmentDateMonth", "res": res, "status_code": 200,
                                             "status_message": "CONTINUE", "date_month": date_month,
                                             "available_slots": available_slots}
                    else:
                        # Handle case where 'results' is empty or not present
                        res = "No available time slots found."
                        response_data_api = {"prevIntent": "appointmentDateMonth", "res": res, "status_code": 200,
                                             "status_message": "FINISH"}
            else:
                print(f"Failed to fetch available time slots. Status Code: {response.status_code}")
                res = "Sorry, I didn't find any slots for the selected time, please call us later"
                response_data_api = {"prevIntent": "appointmentDateMonth", "res": res, "status_code": 200,
                                     "status_message": "FINISH"}

        elif "provide_time" == self.intent and request_data["prevIntent"] == "appointmentDateMonth":
            if any(entity.get("entity") == "time" for entity in self.response_data["entities"]):
                # Find the "time" entity and its value
                time_entity_info = next(
                    (entity for entity in self.response_data["entities"] if entity.get("entity") == "time"), None)

                if time_entity_info and time_entity_info["value"] and request_data["date_month"]:
                    # Extract the "time" entity and its value
                    time_entity = time_entity_info["entity"]
                    time_value = time_entity_info["value"]
                    time_value = time_value.replace(" ", "").replace(".", "").lower()
                    date_mont = request_data.get("date_month")

                    # Matching logic
                    matching_slot = None
                    available_slots1 = request_data.get("available_slots", [])

                    for slot in available_slots1:
                        slot_time = slot.get("time", "").replace(" ", "").replace(".", "").lower()

                        if slot_time == time_value:
                            matching_slot = slot
                            break

                    if matching_slot:
                        doctor_slot_id = matching_slot.get("doctorSlotId", "")
                        res = "Okay great! Can I get your phone number and Name?"
                        response_data_api = {"prevIntent": "provide_time", "res": res, "status_code": 200,
                                             "status_message": "CONTINUE", "time_value": time_value,
                                             "date_month": date_mont,
                                             "doctor_slot_id": doctor_slot_id}

                    else:
                        # No matching doctorSlotId found
                        res = f"Sorry, I couldn't find a matching time slot for {time_value}"
                        response_data_api = {"prevIntent": "provide_time", "res": res, "status_code": 200,
                                             "status_message": "FINISH", "time_value": time_value,
                                             "date_month": request_data.get("date_month")}
                else:
                    # "time" entity is present but has no value
                    print("Time entity not detected. Please repeat this step.")
                    res = "Sorry, I didn't catch the time slot. Can you please provide again?"
                    response_data_api = {"prevIntent": "appointmentDateMonth", "res": res, "status_code": 200,
                                         "status_message": "CONTINUE",
                                         "date_month": request_data.get("date_month"),
                                         "available_slots": request_data.get("available_slots")}
            else:
                # "time" entity is not present, repeat the step
                print("Time entity not detected. Please repeat this step.")
                res = "Sorry, I didn't catch the time slot. Can you please provide again?"
                response_data_api = {"prevIntent": "appointmentDateMonth", "res": res, "status_code": 200,
                                     "status_message": "CONTINUE",
                                     "date_month": request_data.get("date_month"),
                                     "available_slots": request_data.get("available_slots")}

        elif self.intent == "provide_name_number" and (
                request_data["prevIntent"] == "provide_time" or request_data["prevIntent"] == "cancel"
                or request_data["prevIntent"] == "reschedule"):
            if request_data["prevIntent"] == "cancel" or request_data["prevIntent"] == "reschedule":
                if "entities" in self.response_data and len(self.response_data["entities"]) >= 1:
                    mobile_number_temp = None
                    for entity_data in self.response_data["entities"]:
                        entity_type = entity_data["entity"]
                        entity_value = entity_data["value"]
                        if entity_type == "mobile_number":
                            mobile_number_temp = entity_value
                            break;
                    if mobile_number_temp is not None:
                        api_url = f"http://localhost:8000/appointments/removeByMobile/{mobile_number_temp}"
                        response = requests.delete(api_url)

                        # Check the response status
                        if response.status_code == 200:
                            res = "Your appointment is cancelled"
                            response_data_api = {"prevIntent": "provide_name_number", "res": res, "status_code": 200,
                                                 "status_message": "FINISH"}
                        else:
                            # Handle API request failure
                            res = "Error processing your request. Please try again later."
                            response_data_api = {"prevIntent": "provide_name_number", "res": res, "status_code": 500,
                                                 "status_message": "FINISH"}

                if request_data["prevIntent"] == "reschedule":
                    res = "Please select a date and month for reschedule"
                    response_data_api = {"prevIntent": "schedule", "res": res, "status_code": 200,
                                         "status_message": "CONTINUE"}
                return response_data_api

            if "entities" in self.response_data and len(self.response_data["entities"]) >= 2:
                # Iterate through entities to find "name" and "mobile_number"
                name_temp = None
                mobile_number_temp = None

                for entity_data in self.response_data["entities"]:
                    entity_type = entity_data["entity"]
                    entity_value = entity_data["value"]

                    if entity_type == "name" and not name_temp:
                        name_temp = entity_value
                    elif entity_type == "mobile_number" and not mobile_number_temp:
                        mobile_number_temp = entity_value

                if name_temp and mobile_number_temp:
                    print(f"Selected name: {name_temp}")
                    print(f"Selected mobile number: {mobile_number_temp}")
                    time_value = request_data.get("time_value")
                    cleaned_time_value = time_value.replace(" ", "")

                    doctor_id = request_data.get("doctor_slot_id")
                    date_mont = request_data.get("date_month")

                    api_url = f"http://localhost:8000/appointments/create?doctorUuid={doctor_id}&time={cleaned_time_value}&date={date_mont}&patientName={name_temp}&patientMobileNumber={mobile_number_temp}"

                    # Send the API request
                    response = requests.post(api_url)

                    # Check the response status
                    if response.status_code == 201:
                        res = (
                            "Awesome. I have you set up for that time. To cancel or reschedule, please call us again. "
                            "See you soon")
                        response_data_api = {"prevIntent": "provide_name_number", "res": res, "status_code": 200,
                                             "status_message": "FINISH"}
                    else:
                        # Handle API request failure
                        res = "Error processing your appointment. Please try again later."
                        response_data_api = {"prevIntent": "provide_name_number", "res": res, "status_code": 500,
                                             "status_message": "FINISH"}

                else:
                    res = "Sorry, I didn't catch your name or phone number. Can you please provide both?"

                    response_data_api = {"prevIntent": "provide_time", "res": res, "status_code": 200,
                                         "status_message": "CONTINUE",
                                         "time_value": request_data.get("time_value"),
                                         "date_month": request_data.get("date_month"),
                                         "doctor_slot_id": request_data.get("doctorSlotId")}
            else:
                res = "Sorry, I didn't catch your name or phone number. Can you please provide both?"

                response_data_api = {"prevIntent": "provide_time", "res": res, "status_code": 200,
                                     "status_message": "CONTINUE",
                                     "time_value": request_data.get("time_value"),
                                     "date_month": request_data.get("date_month"),
                                     "doctor_slot_id": request_data.get("doctorSlotId")}

        elif "cancel" == self.intent:
            res = "Sure, your appointment has been cancelled."
            print("Bot --> ", res)
            print(" cancel -------------------------------------------")
            res = "Sure, what's your mobile number."
            response_data_api = {"prevIntent": "cancel", "res": res, "status_code": 200,
                                 "status_message": "CONTINUE"}
            # call an external api

        elif self.intent == "repeat":
            response_data_api = {request_data, "status_message", "CONTINUE"}

        else:
            res = "I didn't catch that. Could you please call back later"
            response_data_api = {**request_data, "status_message": "CONTINUE"}

        return response_data_api


app = FastAPI()
chatbot = ChatBot(name="dev")


class ChatBotResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None


class ChatBotInput(BaseModel):
    user_input: str
    data: Optional[dict] = None


@app.post("/chatbot", response_model=ChatBotResponse)
async def chatbot_endpoint(input_data: ChatBotInput):
    user_input = input_data.user_input

    if user_input == "welcome":
        res = "Hello, thanks for calling Dr. Archer’s office. How may I assist you today?"
        response_data = {"prevIntent": "welcome", "res": res, "status_code": 200,
                         "status_message": "CONTINUE"}
        return ChatBotResponse(success=True, message="ChatBot processing success", data=response_data)

    # Access the request data directly from the input_data parameter
    request_data = input_data.data

    chatbot.response_data = chatbot.interact_with_rasa_nlu(user_input)
    chatbot.intent = chatbot.response_data.get("intent", {}).get("name", "")
    response_data = chatbot.process_intent(request_data)

    return ChatBotResponse(success=True, message="ChatBot processing completed", data=response_data)


origins = ["*"]

# Add CORS middleware to the FastAPI app
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8001)
