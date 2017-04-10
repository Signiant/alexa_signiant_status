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

def get_signiant_status():
    '''
    :return: dictionary of services with their respective statuses
    '''
    signiant_services = {}
    request = urllib2.Request(SIGNIANT_STATUS_URL)
    if STATUS_PAGE_API_KEY:
        request.add_header("Authorization", "OAuth %s" % STATUS_PAGE_API_KEY)
    r = urllib2.urlopen(request, timeout=2)
    if r.getcode() == 200:
        response = json.load(r)
        if 'components' in response:
            components = response['components']
            for service in components:
                signiant_services[service['name']] = {'status':service['status']}
    return signiant_services


def convert_status_to_readable(status):
    if 'degraded_performance' in status:
        return "degraded performance"


# ------------------------------ SSML Helpers  ---------------------------------

def pause(duration=1000):
    return '<break time="' + str(duration) + 'ms"/>'


def say_as(interpret_as, msg):
    return '<say-as interpret-as="' + interpret_as + '"> ' + str(msg) + '</say-as>'


def handle_audio(url):
    return "<audio src='" + url + "' />"


# --------------- Helpers that build all of the responses ----------------------

def build_speechlet_response(title, output, reprompt_text, card_output, card_image = None, should_end_session=False):

    outputSpeech = {
        'type': 'SSML',
        'ssml': "<speak>" + output + "</speak>"
    }

    card_type = 'Simple'
    content_key = 'content'
    if card_image:
        card_type = 'Standard'
        content_key = 'text'

    card = {
        'type': card_type,
        'title': title,
        content_key: card_output
    }

    if card_image:
        card['image'] = {'smallImageUrl': card_image}

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
    return get_welcome_response()


def get_welcome_response():
    session_attributes = {}
    card_title = "Welcome"
    speech_output = general_status() + pause()
    reprompt_text = ""
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, speech_output, should_end_session=True))


def handle_session_end_request():
    card_title = "Session Ended"
    speech_output = "Thank you."
    return build_response({}, build_speechlet_response(
        card_title, speech_output, None, speech_output, should_end_session=True))


def general_status():
    signiant_stats = get_signiant_status()

    # Get the number of services
    no_signiant_services = len(signiant_stats)

    signiant_problems = []
    for service in signiant_stats:
        if not 'operational' in signiant_stats[service]['status']:
            signiant_problems.append((service, signiant_stats[service]['status']))

    today = time.strftime("%A %B %d %Y")

    card_output = "Current Signiant Platform Status report for " + today + '\n'
    for service in signiant_stats:
        card_output += service + ': ' + signiant_stats[service]['status'] + '\n'

    speech_output = "Current Signiant Platform Status report for " + today + pause()
    if len(signiant_problems) > 0:
        # We've got a problem
        for service, status in signiant_problems:
            speech_output += service + ' has a status of ' + convert_status_to_readable(status) + pause()
        if len(signiant_problems) < no_signiant_services:
            speech_output += "All other services are operating normally"
    else:
        speech_output += "All services operating normally"

    return speech_output, card_output


def get_status(intent, session):
    session_attributes = {}
    reprompt_text = ""
    card_title = "Signiant Platform Status"
    speech_output = general_status()[0]
    card_output = general_status()[1]

    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, card_output, should_end_session=True))


# --------------- Events ------------------

def on_session_started(session_started_request, session):
    """ Called when the session starts """

    print("on_session_started requestId=" + session_started_request['requestId']
          + ", sessionId=" + session['sessionId'])


def on_launch(launch_request, session):
    """ Called when the user launches the skill without specifying what they
    want
    """

    print("on_launch requestId=" + launch_request['requestId'] +
          ", sessionId=" + session['sessionId'])
    # Dispatch to your skill's launch
    return get_welcome_response()


def on_intent(intent_request, session):
    """ Called when the user specifies an intent for this skill """

    print("on_intent requestId=" + intent_request['requestId'] +
          ", sessionId=" + session['sessionId'])

    intent = intent_request['intent']
    intent_name = intent_request['intent']['name']

    # Dispatch to your skill's intent handlers
    if intent_name == "GetStatus":
        return get_status(intent, session)
    elif intent_name == "AMAZON.HelpIntent":
        return get_help_response()
    elif intent_name == "AMAZON.CancelIntent" or intent_name == "AMAZON.StopIntent":
        return handle_session_end_request()
    else:
        raise ValueError("Invalid intent")


def on_session_ended(session_ended_request, session):
    """ Called when the user ends the session.

    Is not called when the skill returns should_end_session=true
    """
    print("on_session_ended requestId=" + session_ended_request['requestId'] +
          ", sessionId=" + session['sessionId'])
    # add cleanup logic here


# --------------- Main handler ------------------

def lambda_handler(event, context):
    """ Route the incoming request based on type (LaunchRequest, IntentRequest,
    etc.) The JSON body of the request is provided in the event parameter.
    """
    print("event.session.application.applicationId=" +
          event['session']['application']['applicationId'])

    """
    Uncomment this if statement and populate with your skill's application ID to
    prevent someone else from configuring a skill that sends requests to this
    function.
    """
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
