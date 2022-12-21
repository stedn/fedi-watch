"""Example oauth-dropins app. Serves the front page and discovery files.
"""
import importlib
import logging
import urllib.parse

from flask import Flask, render_template, request
import flask
import flask_gae_static
from google.cloud import ndb
from oauth_dropins.webutil import flask_util
from oauth_dropins import mastodon as mstdn
import requests
from werkzeug.exceptions import HTTPException
import time

import datetime
import json

from mastodon import Mastodon, MastodonNotFoundError
from bs4 import BeautifulSoup

from oauth_dropins.webutil import appengine_info, appengine_config

logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=None)
app.json.compact = False
app.config.from_pyfile('config.py')
app.wsgi_app = flask_util.ndb_context_middleware(
    app.wsgi_app, client=appengine_config.ndb_client)
if appengine_info.DEBUG:
  flask_gae_static.init_app(app)

logging.getLogger('requests_oauthlib').setLevel(logging.DEBUG)

start = '/mastodon/start'
callback = '/mastodon/oauth_callback'
app.add_url_rule(start, view_func=mstdn.Start.as_view(start, callback),
                 methods=['POST'])
app.add_url_rule(callback, view_func=mstdn.Callback.as_view(callback, '/'))


@app.errorhandler(Exception)
def handle_discovery_errors(e):
  """A Flask exception handler that handles URL discovery errors.

  Used to catch Mastodon and IndieAuth connection failures, etc.
  """
  if isinstance(e, HTTPException):
    return e

  if isinstance(e, (ValueError, requests.RequestException)):
    logger.warning('', exc_info=True)
    return flask.redirect('/?' + urllib.parse.urlencode({'error': str(e)}))

  return flask_util.handle_exception(e)


@app.route('/')
def home_page():
  """Renders and serves the home page."""
  vars = dict(request.args)
  vars.update({
    'mastodon_html': mstdn.Start.button_html(
      '/mastodon/start', image_prefix='/static/',
      outer_classes='col-md-3 col-sm-4 col-xs-6')
  })

  key = request.args.get('auth_entity')
  if key:
    vars['entity'] = ndb.Key(urlsafe=key).get()

  return render_template('index.html', **vars)


# @app.route("/poll_local_timelines")
# def poll_local_timelines():
#     apps = mstdn.MastodonApp.query().fetch()
#     counter = {}
#     total_counter=0
#     shuffle_apps = {}
#     for a in apps:
#       shuffle_apps[a.instance]= mstdn.MastodonAuth.query(mstdn.MastodonAuth.app == a.key).fetch()
#       counter[a.instance]=0
#     while shuffle_apps:
#       for instance in list(shuffle_apps.keys()):
#         if len(shuffle_apps[instance])==0:
#           shuffle_apps.pop(instance)
#         else:
#           auth = shuffle_apps[instance].pop()
#           masto = Mastodon(
#               access_token = auth.access_token_str,
#               api_base_url = instance
#           )
#           for item in masto.timeline_local():
#             q = mstdn.TimelineWatch.query(mstdn.TimelineWatch.instance == instance,
#                                           mstdn.TimelineWatch.id == item['id']).fetch(1)
#             if len(q)==0:
#               toWatch = mstdn.TimelineWatch(id=item['id'], instance=instance, url=item['url'], content=item['content'])
#               toWatch.put()
#               counter[instance]+=1
#               total_counter+=1
#           time.sleep(10)

#     return f'<p> Added {total_counter} posts to timeline watcher.</p><p><a href="/check_for_descendants">Click here to poll for replies</a></p>'

# @app.route("/check_for_descendants")
# def check_for_descendants():
#     import detoxify

#     detox = detoxify.Detoxify(checkpoint='unbiased-albert-c8519128.ckpt', huggingface_config_path='huggingface_model_path/', device='cpu')
#     apps = mstdn.MastodonApp.query().fetch()
#     counter = {}
#     subtractor = {}
#     total_counter = 0
#     total_subtractor = 0
#     shuffle_apps = {}
#     for a in apps:
#       shuffle_apps[a.instance]= mstdn.MastodonAuth.query(mstdn.MastodonAuth.app == a.key).fetch()
#       counter[a.instance]=0
#       subtractor[a.instance]=0
#     while shuffle_apps:
#       for instance in list(shuffle_apps.keys()):
#         print(instance)
#         if len(shuffle_apps[instance])==0:
#           shuffle_apps.pop(instance)
#         else:
#           timelinewatch = mstdn.TimelineWatch.query(mstdn.TimelineWatch.instance == instance).order(mstdn.TimelineWatch.last_checked_at).fetch()
#           print(timelinewatch)
#           for t in timelinewatch:
#             t.last_checked_at = datetime.datetime.now()
#             print(t)
#             t.put()
#           auth = shuffle_apps[instance].pop()
#           masto = Mastodon(
#               access_token = auth.access_token_str,
#               api_base_url = instance
#           )

#           for item in timelinewatch:
#             if (datetime.datetime.now() - item.created_at).total_seconds() > 24*60:
#               item.key.delete()
#               subtractor[instance]+=1
#               total_subtractor+=1
#             else:
#               try:
#                 desc = masto.status_context(item.id)['descendants']
#                 for r in desc:
#                   q = mstdn.ReplyCheck.query(mstdn.ReplyCheck.instance == instance,
#                                             mstdn.ReplyCheck.id == r['id']).fetch(1)
#                   if len(q)==0:
#                     counter[instance]+=1
#                     total_counter+=1
#                     toot_text = BeautifulSoup(r['content']).get_text()
#                     print(toot_text)
#                     report = False
#                     scores = detox.predict(toot_text)
#                     for attribute in scores:#config['thresholds'].keys():
#                       score = scores[attribute]
#                       print(f"{attribute}: {score}")
#                       if score > 0.01:
#                           report = True
#                           break # no need to continue checking
#                     replyWatch = mstdn.ReplyCheck(id=r['id'], instance=instance, url=r['url'], content=r['content'], report=report, covered=False, score=json.dumps({k:f"{scores[k]:.2%}" for k in scores}))
#                     replyWatch.put()

#               except MastodonNotFoundError:
#                 item.key.delete()
#                 subtractor[instance]+=1
#                 total_subtractor+=1
#           time.sleep(10)

#     return f'<p> Added {total_counter} replies to reply list, stopped tracking {total_subtractor} posts, </p><p><a href="/display_replies">Click here to view all replies</a></p>'

# @app.route("/remove_old_replies")
# def remove_old_replies():
#     total_subtractor = 0
#     replycheck = mstdn.ReplyCheck.query().order(mstdn.ReplyCheck.last_checked_at).fetch()
#     for item in replycheck:
#       if (datetime.datetime.now() - item.created_at).total_seconds() > 24*60:
#         item.key.delete()
#         subtractor[instance]+=1
#         total_subtractor+=1

#     return f'<p> Stopped tracking {total_subtractor} replies, </p><p><a href="/display_replies">Click here to view all replies</a></p>'


@app.route('/tst')
def tst():
    """
    Generate a random number every 2 seconds and emit to a socketio instance (broadcast)
    Ideally to be run in a separate thread?
    """
    #infinite loop of magical random numbers
    print("Making random numbers")
    reply_checks = mstdn.ReplyCheck.query().order(-mstdn.ReplyCheck.created_at).fetch()
    return_string = ''
    for r in reply_checks:
      scores = json.loads(r.score)
      score_str = ' '.join([f'<li>{k}: {scores[k]}</li>' for k in scores])
      return_string += f'''<div><p>Post #{r.id}: <a href="{r.url}" target="_blank"> {r.url}</a></p>
      <p>Report: {r.report} </p>
      <p>Score: </p><ul>{score_str} </ul>
      <p>Content: {r.content}</p></div>
      <hr/>'''
    return {'body':return_string}

@app.route('/display_replies')
def display_replies():
    #only by sending this page first will the client be connected to the socketio instance
    return render_template('poll.html')