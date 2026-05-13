import logging
from msgraph import GraphServiceClient
from azure.identity import DeviceCodeCredential

def graph_get_upcoming_events(*args, **kwargs): return "Mocked"
def graph_read_inbox(*args, **kwargs): return "Mocked"
def graph_create_reply_draft(*args, **kwargs): return "Mocked"
def graph_send_mail(*args, **kwargs): return "Mocked"
def graph_create_event(*args, **kwargs): return "Mocked"
def create_graph_client(credential): return GraphServiceClient(credential)
