from google.cloud import datastore

# Instantiates a client
datastore_client = datastore.Client()
kind = "user"

def check_existence_of_attribute(column_name, value):
	query = datastore_client.query(kind=kind).add_filter(column_name, '=', value)
	resultset = list(query.fetch())

	return len(resultset)
