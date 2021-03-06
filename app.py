#!/usr/bin/python
from flask import Flask, request, Response
from flask_dataset import Dataset
import json
import requests

# -- Application Setup
app = Flask(__name__)
app.config['DATASET_DATABASE_URI'] = 'sqlite:///:memory:'
db = Dataset(app)


# -- Add default route (/) for basic health check
@app.route('/', methods=['GET'])
def return_blank():
    return ""


# -- Add route to GET status for a task
@app.route('/api/status/<messageid>', methods=['GET'])
def get_status(messageid):
    table = db['msgbus']
    messages = table.find(id=messageid)
    mcount = table.count(id=messageid)
    resp = ""
    if mcount == 0:
        # If there is not a task with the specified ID, return 404
        resp = Response("", status=404, mimetype='application/json')
    else:
        # Loop through tasks (should only be one), add to json array
        arr_messages = []
        for message in messages:
            arr_messages.append(json.loads(json.dumps(message)))
        resp = json.dumps(arr_messages)
    return resp


# -- Add route to POST new status for a task
@app.route('/api/status/<messageid>', methods=['POST'])
def update_status(messageid):
    content = request.get_json(force=True)
    newstatus = content['status']
    resp = ""
    with app.test_request_context():
        message = db['msgbus'].find_one(id=messageid)
        # If the task exists, perform an update
        if message is not None:
            retval = UpdateStatus(message, newstatus)
        else:
            retval = 0
        if retval == 0:
            # If the task does not exist, or if there was a problem, return 404
            resp = Response("", status=404, mimetype='application/json')
        else:
            # Return 200 ok
            resp = Response("", status=200, mimetype='application/json')
    return resp


# -- Add route to POST update for a task
@app.route('/api/update/<messageid>', methods=['POST'])
def update_message(messageid):
    content = request.get_json(force=True)
    messageupdate = content['msgresp']
    resp = ""
    with app.test_request_context():
        message = db['msgbus'].find_one(id=messageid)
        # If the task exists, perform an update
        if message is not None:
            data = dict(id=messageid, msgresp=messageupdate)
            retval = db['msgbus'].update(data, ['id'])
            retval = UpdateStatus(message, "2")
        else:
            retval = 0
        if retval == 0:
            # If the task does not exist, or if there was a problem, return 404
            resp = Response("", status=404, mimetype='application/json')
        else:
            # Return 200 ok
            resp = Response("", status=200, mimetype='application/json')
    return resp


# -- Add route to DELETE all tasks for a specified channel
@app.route('/api/send/<channelid>', methods=['DELETE'])
def clear_bus(channelid):
    # Default return 204 deleted
    resp = Response("", status=204, mimetype='application/json')
    with app.test_request_context():
        mcount = db['msgbus'].count(chid=channelid)
        # If there are no tasks for the specified collector, return 404
        if mcount == 0:
            resp = Response("", status=404, mimetype='application/json')
        else:
            db['msgbus'].delete(chid=channelid)
    return resp


# -- Add route to POST new task for a specified channel
@app.route('/api/send/<channelid>', methods=['POST'])
def send_message(channelid):
    content = request.get_json(force=True)
    content['chid'] = channelid
    # Add new task to the queue for the specified channel
    with app.test_request_context():
        retval = db['msgbus'].insert(content)
    text = str(retval)
    return text


# -- Add route to GET all channels on the bus
@app.route('/api/get', methods=['GET'])
def get_message_channels():
    table = db['msgbus']
    messages = table.find()
    mcount = db['msgbus'].count()
    # If there are no channels found, return 404 not found
    if mcount == 0:
        resp = Response("", status=404, mimetype='application/json')
    else:
        # If there are messages, loop through and dump in json array
        arr_messages = {}
        for message in messages:
            channelid = message["chid"]
            if channelid not in arr_messages:
                arr_messages[channelid] = {}

            taskid = message["id"]
            if "status" in message:
                taskstatus = message["status"]
            else:
                taskstatus = "0"
            arr_messages[channelid][taskid] = taskstatus
        resp = json.dumps(arr_messages)
    return resp


# -- Add route to GET all tasks for specified channel, force return messages
@app.route('/api/get/<channelid>/force', methods=['GET'])
def get_message_force(channelid):
    table = db['msgbus']
    messages = table.find(chid=channelid)
    mcount = db['msgbus'].count(chid=channelid)
    # If there are no messages for the specified channel, return 404 not found
    if mcount == 0:
        resp = Response("", status=404, mimetype='application/json')
    else:
        # If there are tasks, loop through and dump in json array
        arr_messages = []
        for message in messages:
            doset = 0
            if "status" in message:
                if message["status"] == "" or message["status"] == "0":
                    doset = 1
            else:
                doset = 1

            arr_messages.append(json.loads(json.dumps(message)))

            if doset == 1:
                UpdateStatus(message, "1")
        resp = json.dumps(arr_messages)
    return resp


# -- Add route to GET all tasks for specified channel
@app.route('/api/get/<channelid>', methods=['GET'])
def get_message(channelid):
    table = db['msgbus']
    messages = table.find(chid=channelid)
    mcount = db['msgbus'].count(chid=channelid)
    # If there are no messages for the specified channel, return 404 not found
    if mcount == 0:
        resp = Response("", status=404, mimetype='application/json')
    else:
        # If there are tasks, loop through and dump in json array
        arr_messages = []
        for message in messages:
            doset = 0
            if "status" in message:
                if message["status"] == "" or message["status"] == "0":
                    arr_messages.append(json.loads(json.dumps(message)))
                    doset = 1
            else:
                arr_messages.append(json.loads(json.dumps(message)))
                doset = 1

            if doset == 1:
                UpdateStatus(message, "1")
        resp = json.dumps(arr_messages)
    return resp


# -- Function used to update status on a task - used when manual task update is
# POSTed or when a GET is done for all tasks
def UpdateStatus(message, newstatus):
    messageid = message['id']
    url = ""
    if 'webhook' in message:
        url = message['webhook']

    headers = {
        'content-type': 'application/json'
    }
    hookdata = {"id": str(messageid), "status": str(newstatus)}
    jsondata = json.dumps(hookdata)

    data = dict(id=messageid, status=newstatus)
    retval = db['msgbus'].update(data, ['id'])
    # if a webhook was specified, call the webhook since there was an update
    if url != "":
        requests.request("POST", url, data=jsondata, headers=headers)
    return retval


# -- Main function
if __name__ == '__main__':
    # Run Flask
    app.run(debug=True, host='0.0.0.0', port=int("5000"))
