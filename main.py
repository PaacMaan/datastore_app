from flask import Flask, Response, flash, jsonify, render_template, request, session, redirect, url_for
import secrets
from werkzeug import secure_filename
from util import *
from datetime import datetime

from google.cloud import datastore
from google.cloud import storage

# Initiating the Flask app
app = Flask(__name__)

# Instantiates a client
datastore_client = datastore.Client()
storage_client = storage.Client()

# The kind of the entity saved
kind = "user"
# The name for the new bucket
CLOUD_STORAGE_BUCKET = "forum_user_images"

# set the app secret key
app.secret_key = secrets.token_urlsafe(16)



@app.route("/login", methods=["GET", "POST"])
def login():
	if request.method == "GET":
		return render_template('login.html')
	elif request.method == 'POST':
		# get the user data from the form
		user_id = request.form['user_id']
		user_password = int(request.form['user_password'])
		
		# check their existence in cloud datastore
		query = datastore_client.query(kind=kind).add_filter('id', '=', user_id).add_filter('password', '=', user_password).fetch()
		
		# fetch results
		resultset = [dict(elm) for elm in list(query)]
		print(resultset)
		# check if the user doesn't exist
		if len(resultset) == 0:
			return jsonify({"response": "id or password invalid"})

		# user exist so we redirect to a new page
		session['user'] = resultset[0]

		return redirect(url_for('forum'))


@app.route("/register", methods=["GET", "POST"])
def register():
	if request.method == "GET":
		return render_template("register.html")
	elif request.method == "POST":
		# get the user data from the form
		user_id = request.form['user_id']
		username = request.form["user_name"]
		user_password = int(request.form['user_password'])
		# user image
		user_image = request.files['user_image']

		# check their id exist in the user kind
		found_id = check_existence_of_attribute("id", user_id)
		if found_id != 0:
			return jsonify({"response": "user id already exist"})

		# check if the username exist already
		found_username = check_existence_of_attribute("user_name", username)
		if found_username != 0:
			return jsonify({"response": "username already exist"})

		try:
			# in case user doesn't already exist insert the new entity
			user = datastore.Entity(datastore_client.key("user"))
			user.update(
			    {
			        "id": user_id,
			        "user_name": username,
			        "password": user_password
			    }
			)
			datastore_client.put(user)

			if not user_image:
				return 'No file uploaded.', 400

			# Get the bucket that the file will be uploaded to.
			bucket = storage_client.get_bucket(CLOUD_STORAGE_BUCKET)
			
			# Create a new blob and upload the file's content.
			blob = bucket.blob(user_image.filename)

			blob.upload_from_string(
			    user_image.read(),
			    content_type=user_image.content_type
			)
			url = blob.public_url
			return redirect(url_for('login'))
		except Exception as e:
			return jsonify({"response": "There was an exception while inserting the new user, try again"})


@app.route("/forum", methods=["GET", "POST"])
def forum():
	if request.method == "GET":
		# get last top 10 messages to show in the forum page
		query = datastore_client.query(kind="message").fetch(limit=10)
		
		# fetch results
		resultset = [dict(elm) for elm in list(query)]

		return render_template("index.html", resultset=resultset)
	elif request.method == "POST":
		# get the data from the form
		subject = request.form["subject"]
		message_text = request.form["message"]
		post_image = request.files["post_image"]

		try:
			# save the image to gcs
			if not post_image:
				return 'No file uploaded.', 400

			# Get the bucket that the file will be uploaded to.
			bucket = storage_client.get_bucket(CLOUD_STORAGE_BUCKET)
			
			# Create a new blob and upload the file's content.
			blob = bucket.blob(post_image.filename)

			blob.upload_from_string(
			    post_image.read(),
			    content_type=post_image.content_type
			)
			image_url = blob.public_url

			# get the user from session
			user = session["user"]

			# save the message into datastore 
			message = datastore.Entity(datastore_client.key("message"))
			message.update(
			    {
			        "image_url": image_url,
			        "message_text": message_text,
			        "subject": subject,
			        "published_by": user["user_name"],
			        "message_date": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
			    }
			)
			datastore_client.put(message)

			return redirect(url_for('forum'))
		except:
			return jsonify({"response": "There was an exception while inserting the new message, try again"})


@app.route('/logout', methods=['GET'])
def logout():
    # unset session variable
    session.pop('username', None)
    # return to index
    return render_template('login.html')

from google.cloud.datastore.key import Key

@app.route("/user_page/", methods=["GET", "POST"])
def user_page():
	if request.method == "GET":
		# get messages published by the user in the current session
		username = session["user"]["user_name"]
		query = datastore_client.query(kind="message").add_filter('published_by', "=", username).fetch()

		# prepare the list of our resultset
		resultset = []
		for elm in list(query):
			# print(elm) #dict
			loc = {}
			for prop, value in dict(elm).items():
				loc[prop] = value
				loc["message_id"] = elm.id
			resultset.append(loc)

		return render_template('user_page.html', resultset=resultset)
	elif request.method == "POST":
		if request.form["edit"] == "Save changes":
			# get the user data
			subject = request.form["msg_subject"]
			msg_body = request.form["msg_text"]
			post_image = request.files["post_image"]
			post_id = request.form["post_id"]

			try:
				# save the image to gcs
				if not post_image:
					return 'No file uploaded.', 400

				# Get the bucket that the file will be uploaded to.
				bucket = storage_client.get_bucket(CLOUD_STORAGE_BUCKET)
			
				# Create a new blob and upload the file's content.
				blob = bucket.blob(post_image.filename)

				blob.upload_from_string(
				    post_image.read(),
				    content_type=post_image.content_type
				)
				image_url = blob.public_url
				
				resultset = datastore_client.query(kind="message").add_filter('__key__', '=', datastore_client.key("message", int(post_id)) ).fetch()
				
				for p in resultset:
					p["subject"] = subject
					p["message_text"] = msg_body
					p["image_url"] = image_url
					p["message_date"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
					datastore_client.put(p)

				return redirect(url_for('forum'))
			except Exception as e:
				raise jsonify({"response": "There was an exception while inserting the new message, try again"})


			print(subject, msg_body)
			return jsonify({"response":"ok"})
		else:
			# get older pasword
			current_password = request.form["old_password"]
			new_password = request.form["new_password"]

			# get the user from session
			user = session["user"]
			# get the actual password from session
			real_password = user["password"]

			if str(real_password) != current_password:
				return jsonify({"response" : "The old password is incorrect"})

			query = datastore_client.query(kind="user")
			query.add_filter('password', '=', int(current_password))
			data = query.fetch()

			for u in data:
				u["password"] = int(new_password)
				datastore_client.put(u)

			return redirect(url_for('logout'))

@app.route("/test")
def test():
	# get last top 10 messages to show in the forum page
	query = datastore_client.query(kind="message").fetch(limit=10)
	
	# fetch results
	resultset = [dict(elm) for elm in list(query)]
	return jsonify({"response": resultset})

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)