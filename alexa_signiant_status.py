"""
Return Signiant Platform Status
"""

from __future__ import print_function
import time
import urllib2
import json
import os

# Default Signiant Status Page URL
SIGNIANT_STATUS_URL = 'https://1dmtgkjnl3y3.statuspage.io/api/v2/summary.json'
STATUS_PAGE_API_KEY = None

# We need this to be set as an env var - fail if it's not
if 'applicationId' in os.environ:
    APPLICATION_ID = os.environ['applicationId']
else:
    raise ValueError("No Application ID provided")

if 'statusPageUrl' in os.environ:
    SIGNIANT_STATUS_URL = os.environ['statusPageUrl']
if 'statusPageApiKey' in os.environ:
    STATUS_PAGE_API_KEY = os.environ['statusPageApiKey']


def get_raw_component_status():
    '''
    :return: list of services with their info
    '''
    sig_components = []
    request = urllib2.Request(SIGNIANT_STATUS_URL)
    if STATUS_PAGE_API_KEY:
        request.add_header("Authorization", "OAuth %s" % STATUS_PAGE_API_KEY)
    r = urllib2.urlopen(request, timeout=2)
    if r.getcode() == 200:
        response = json.load(r)
        if 'components' in response:
            sig_components = response['components']
    return sig_components


def get_signiant_status():
    raw_status_list = get_raw_component_status()
    # {
    #     "status": "operational",
    #     "name": "v1",
    #     "created_at": "2016-10-21T14:20:42.069Z",
    #     "updated_at": "2016-12-02T20:54:28.202Z",
    #     "position": 1,
    #     "description": "Backend services for TAPIv1",
    #     "group_id": "1234567890",
    #     "showcase": false,
    #     "id": "2345678901",
    #     "page_id": "123abc456def",
    #     "group": false,
    #     "only_show_if_degraded": false
    # }
    # Find the groups
    groups = {}
    for component in raw_status_list:
        if component['group']:
            groups[component['id']] = component['name']
    # Get statuses
    signiant_services = {}
    for service in raw_status_list:
        if service['group_id']:
            # This is part of a group - get the group's name
            name = groups[service['group_id']] + ' ' + service['name']
            status = service['status']
            signiant_services[name] = {'status': status}
    return signiant_services


def convert_status_to_readable(status):
    if 'degraded_performance' in status:
        return "degraded performance"
    elif 'major_outage' in status:
        return "major outage"
    elif 'partial_outage' in status:
        return "partial outage"
    elif 'under_maintenance' in status:
        return "under maintenance"
    else:
        return status


# ------------------------------ SSML Helpers  ---------------------------------

def pause(duration=1000):
    return '<break time="' + str(duration) + 'ms"/>'


def say_as(interpret_as, msg):
    return '<say-as interpret-as="' + interpret_as + '"> ' + str(msg) + '</say-as>'


def handle_audio(url):
    return "<audio src='" + url + "' />"


# --------------- Helpers that build all of the responses ----------------------

def build_speechlet_response(title, output, card_output, reprompt_text="",
                             card_image_small=None, card_image_large=None,
                             should_end_session=False):

    outputSpeech = {
        'type': 'SSML',
        'ssml': "<speak>" + output + "</speak>"
    }

    card = {}
    card['title'] = title
    if card_image_small or card_image_large:
        card['type'] = 'Standard'
        card['text'] = card_output
        card['image'] = {}
        if card_image_small:
            card['image']['smallImageUrl'] = card_image_small
        if card_image_large:
            card['image']['largeImageUrl'] = card_image_large
    else:
        card['type'] = 'Simple'
        card['content'] = card_output

    reprompt = {
        'outputSpeech': {
            'type': 'SSML',
            'ssml': "<speak>" + reprompt_text + "</speak>"
        }
    }

    return {
        'outputSpeech': outputSpeech,
        'card': card,
        'reprompt': reprompt,
        'shouldEndSession': should_end_session
    }


def build_response(session_attributes, speechlet_response):
    return {
        'version': '1.0',
        'sessionAttributes': session_attributes,
        'response': speechlet_response
    }


# --------------- Functions that control the skill's behavior ------------------

def get_help_response():
    card_title = "Signiant Help"
    speech_output = "To request information about Signiant Platform Status, say status report" + pause() \
                    + "What can I help you with?"
    reprompt_text = "What can I help you with?"
    return build_response({}, build_speechlet_response(
        card_title, speech_output, speech_output, reprompt_text, should_end_session=False))


def get_welcome_response():
    session_attributes = {}
    return get_status()


def handle_session_end_request():
    card_title = "Session Ended"
    speech_output = "Thank you."
    return build_response({}, build_speechlet_response(
        card_title, speech_output, speech_output, should_end_session=True))


def general_status():
    signiant_stats = get_signiant_status()
    # Get the number of services
    no_signiant_services = len(signiant_stats)

    signiant_problems = []
    for service in signiant_stats:
        if not 'operational' in signiant_stats[service]['status']:
            signiant_problems.append((service, signiant_stats[service]['status']))

    today = time.strftime("%A %B %d %Y")
    now = time.strftime("%X UTC")

    card_output = "Current Signiant Platform Status report for " + today + ' at ' + now + '\n'
    for service in signiant_stats:
        card_output += service + ': ' + signiant_stats[service]['status'] + '\n'
    card_output += "For more information, please visit status.signiant.com"

    speech_output = "Current Signiant Platform Status report for " + today + pause()
    if len(signiant_problems) > 0:
        # We've got a problem
        for service, status in signiant_problems:
            speech_output += service + ' has a status of ' + convert_status_to_readable(status) + pause()
        if len(signiant_problems) < no_signiant_services:
            speech_output += "All other services are operating normally" + pause()
        speech_output += "For more information, please visit status.signiant.com"
    else:
        speech_output += "All services operating normally"

    return speech_output, card_output


def get_status():
    session_attributes = {}
    card_title = "Signiant Platform Status"
    speech_output, card_output = general_status()

    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, card_output, should_end_session=True))


# --------------- Events ------------------

def on_session_started(session_started_request, session):
    """
    Called when the session starts
    """

    print("on_session_started requestId=" + session_started_request['requestId']
          + ", sessionId=" + session['sessionId'])


def on_launch(launch_request, session):
    """
    Called when the user launches the skill without specifying what they want
    """

    print("on_launch requestId=" + launch_request['requestId'] +
          ", sessionId=" + session['sessionId'])
    # Dispatch to your skill's launch
    return get_welcome_response()


def on_intent(intent_request, session):
    """
    Called when the user specifies an intent for this skill
    """

    print("on_intent requestId=" + intent_request['requestId'] +
          ", sessionId=" + session['sessionId'])

    intent = intent_request['intent']
    intent_name = intent_request['intent']['name']

    # Dispatch to your skill's intent handlers
    if intent_name == "GetStatus":
        #return get_status(intent, session)
        return get_status()
    elif intent_name == "AMAZON.HelpIntent":
        return get_help_response()
    elif intent_name == "AMAZON.CancelIntent" or intent_name == "AMAZON.StopIntent":
        return handle_session_end_request()
    else:
        raise ValueError("Invalid intent")


def on_session_ended(session_ended_request, session):
    """
    Called when the user ends the session.
    Is not called when the skill returns should_end_session=true
    """
    print("on_session_ended requestId=" + session_ended_request['requestId'] +
          ", sessionId=" + session['sessionId'])


# --------------- Main handler ------------------

def lambda_handler(event, context):
    """
    Route the incoming request based on type (LaunchRequest, IntentRequest,
    etc.) The JSON body of the request is provided in the event parameter.
    """
    print("event.session.application.applicationId=" +
          event['session']['application']['applicationId'])

    if (event['session']['application']['applicationId'] != APPLICATION_ID):
        raise ValueError("Invalid Application ID")

    if event['session']['new']:
        on_session_started({'requestId': event['request']['requestId']},
                           event['session'])

    if event['request']['type'] == "LaunchRequest":
        return on_launch(event['request'], event['session'])
    elif event['request']['type'] == "IntentRequest":
        return on_intent(event['request'], event['session'])
    elif event['request']['type'] == "SessionEndedRequest":
        return on_session_ended(event['request'], event['session'])
