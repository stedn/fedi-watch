from google.cloud import datastore
import time

import datetime
import json

from mastodon import Mastodon, MastodonNotFoundError
from bs4 import BeautifulSoup

import detoxify
import pytz

detox = detoxify.Detoxify(checkpoint='unbiased-albert-c8519128.ckpt', huggingface_config_path='huggingface_model_path/', device='cpu')

def poll_local_timelines():
    client = datastore.Client()
    apps = client.query(kind='MastodonApp').fetch()
    counter = {}
    shuffle_apps = {}
    for a in apps:
      shuffle_apps[a['instance']]= list(client.query(kind='MastodonAuth').add_filter("app", "=", a.key).fetch())
      counter[a['instance']]=0
    while shuffle_apps:
      for instance in list(shuffle_apps.keys()):
        if len(shuffle_apps[instance])==0:
          shuffle_apps.pop(instance)
        else:
          auth = shuffle_apps[instance].pop()
          masto = Mastodon(
              access_token = auth['access_token_str'],
              api_base_url = instance
          )
          for item in masto.timeline_local():
            q = list(client.query(kind='TimelineWatch').add_filter('instance', '=', instance).add_filter('id', '=', item['id']).fetch(1))
            if len(q)==0:
              with client.transaction():
                task = datastore.Entity(key=client.key("TimelineWatch"))
                task.update(
                    {
                        "id": item['id'],
                        "instance": instance,
                        "url": item['url'],
                        "created_at": datetime.datetime.utcnow().replace(tzinfo=pytz.UTC),
                        "last_checked_at": datetime.datetime.utcnow().replace(tzinfo=pytz.UTC),
                    }
                )
                client.put(task)
              counter[instance]+=1
          time.sleep(5)
    print('Timeline Watch posts added:')
    print(counter)



def check_for_descendants():
    client = datastore.Client()
    apps = client.query(kind='MastodonApp').fetch()
    counter = {}
    subtractor = {}
    shuffle_apps = {}
    for a in apps:
      shuffle_apps[a['instance']]= list(client.query(kind='MastodonAuth').add_filter("app", "=", a.key).fetch())
      counter[a['instance']]=0
      subtractor[a['instance']]=0
    while shuffle_apps:
      for instance in list(shuffle_apps.keys()):
        if len(shuffle_apps[instance])==0:
          shuffle_apps.pop(instance)
        else:
          timelinewatch = list(client.query(kind='TimelineWatch',order=['last_checked_at']).add_filter("instance", "=", instance).fetch())
          print(len(timelinewatch))
          auth = shuffle_apps[instance].pop()
          masto = Mastodon(
              access_token = auth['access_token_str'],
              api_base_url = instance
          )

          for item in timelinewatch:
            if (datetime.datetime.utcnow().replace(tzinfo=pytz.UTC) - item['created_at']).total_seconds() > 3*60:
              client.delete(item.key)
              subtractor[instance]+=1
            else:
              try:
                desc = masto.status_context(item['id'])['descendants']
                for r in desc:
                  q = list(client.query(kind='ReplyCheck').add_filter("instance", "=", instance).add_filter("id", "=", r['id']).fetch(1))
                  if len(q)==0:
                    counter[instance]+=1
                    toot_text = BeautifulSoup(r['content']).get_text()
                    report = False
                    scores = detox.predict(toot_text)
                    for attribute in scores:#config['thresholds'].keys():
                      score = scores[attribute]
                      if score > 0.01:
                          report = True
                          break # no need to continue checking
                    with client.transaction():
                      rw = datastore.Entity(key=client.key("ReplyCheck"))
                      rw.update(
                          {
                              "id": r['id'],
                              "instance": instance,
                              "url": r['url'],
                              "content": r['content'],
                              "created_at": datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
                              "report": report,
                              "covered": False,
                              "score": json.dumps({k:f"{scores[k]:.2%}" for k in scores}),
                          }
                      )
                      client.put(rw)

                item['last_checked_at'] = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
                client.put(item)

              except MastodonNotFoundError:
                client.delete(item.key)
                subtractor[instance]+=1
          time.sleep(5)
    print('TimelineWatch posts removed:')
    print(subtractor)
    print('replyCheck replies added:')
    print(counter)


def remove_old_replies():
    client = datastore.Client()
    total_subtractor = 0
    replycheck = list(client.query(kind='ReplyCheck',order=['created_at']).fetch())
    for item in replycheck:
      if (datetime.datetime.utcnow().replace(tzinfo=pytz.UTC) - item['created_at']).total_seconds() > 60:
        if not item['report']:
          client.delete(item.key)
          total_subtractor+=1

    print('ReplyCheck replies deleted:',total_subtractor)


if __name__ == "__main__":
    print(datetime.datetime.now())
    poll_local_timelines()
    check_for_descendants()
    remove_old_replies()
