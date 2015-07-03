#
# Copyright 2015 NEC Corporation.
#
# Authors: Ryota Mibu <r-mibu@cq.jp.nec.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import oslo_messaging

from ceilometer import messaging


ALARM_TYPE_EVENT = 'event'
EVENT_ALARM_RPC_TOPIC = 'alarm.all'


def get_event_listener(evaluators):
    return messaging.get_notification_listener(
        messaging.get_transport(),
        [oslo_messaging.Target(EVENT_ALARM_RPC_TOPIC)],
        [EventAlarmEndpoint(evaluators)])


class EventAlarmEndpoint(object):

    def __init__(self, evaluators):
        self.evaluator = evaluators[ALARM_TYPE_EVENT]

    def sample(self, ctxt, publisher_id, event_type, payload, metadata):
        # TODO(r-mibu): requeue on error
        self.evaluator.evaluate_events(payload)
