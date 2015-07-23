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

import fnmatch
import operator

from oslo_log import log

from ceilometer.alarm import evaluator
from ceilometer.i18n import _

LOG = log.getLogger(__name__)

COMPARATORS = {
    'gt': operator.gt,
    'lt': operator.lt,
    'ge': operator.ge,
    'le': operator.le,
    'eq': operator.eq,
    'ne': operator.ne,
}
PROJECT_NONE = ''


class EventAlarmEvaluator(evaluator.Evaluator):

    def evaluate_events(self, events):
        """Evaluate the events by referring related alarms."""

        if not isinstance(events, list):
            events = [events]

        LOG.debug(_('start event alarm evaluation: #events = %d'), len(events))
        for event in events:
            LOG.debug(_('evaluate event: event = %s') % event)

            if not self._validate_event(event):
                LOG.debug(_('aborting evaluation of the event'))
                continue

            for alarm in self._related_alarms(event):
                try:
                    if self._evaluate_event_alarm(event, alarm):
                        self._fire_alarm(event, alarm)
                except Exception:
                    LOG.exception(_('Failed to evaluate alarm %s'),
                                  alarm.alarm_id)

        LOG.debug(_('finished event alarm evaluation'))

    @staticmethod
    def _validate_event(event):
        """Validate received event has mandatory parameters."""

        if event.get('event_type') and event.get('message_id'):
            return True

        LOG.error(_('Failed to extract event_type from event %s'), event)
        return False

    def _related_alarms(self, event):
        """Get all alarms defined in the project."""

        traits = event.get('traits') or {}
        project_id = (traits.get('tenant_id') or traits.get('project_id') or
                      PROJECT_NONE)

        # TODO(r-mibu): cache alarm definitions
        enabled = {'field': 'enabled', 'value': True}
        type_event = {'field': 'type', 'value': 'event'}
        project = {'field': 'project_id', 'value': project_id}
        alarms = self._client.alarms.list(q=[enabled, type_event, project])
        return alarms

    def _evaluate_event_alarm(self, event, alarm):
        """Evaluate the event by referring the alarm definition.

        This function compares each condition of the alarm and return whether
        alarm have to be fired or not on the assumption that all conditions
        are combined by AND operator.
        When the received event met conditions defined in alarm 'event_type'
        and 'query', the alarm will be updated to state='alarm' (alarmed).
        Note: by this evaluator, the alarm won't be changed to state='ok'
        neither state='insufficient data'.
        """

        LOG.debug(_('evaluating event alarm %s') % alarm.alarm_id)

        if not alarm.repeat_actions and alarm.state == evaluator.ALARM:
            LOG.debug(_('skip alarm which have already fired'))
            return False

        event_pattern = alarm.rule['event_type']
        if fnmatch.fnmatch(event['event_type'], event_pattern):
            LOG.debug(_('aborting evaluation of the alarm due to '
                        'uninterested event_type'))
            return False

        def _compare(condition):
            op = COMPARATORS[condition.get('op', 'eq')]
            value = event
            for f in condition['field'].split('.'):
                value = value.get(f)
                if not value:
                    break
            LOG.debug(_('comparing value %(value)s against condition '
                        '%(condition)s') %
                      {'value': value, 'condition': condition})
            return op(value, condition['value'])

        for condition in alarm.rule['query']:
            if not _compare(condition):
                LOG.debug(_('aborting evaluation of the alarm due to '
                            'unmet condition %s'), condition)
                return False

        return True

    def _fire_alarm(self, event, alarm):
        """Update alarm state and fire alarm via alarm notifier."""

        state = evaluator.ALARM
        reason = (_('Event message_id=%(message)s hit query of alarm '
                    'id=%(alarm)s')
                  % {'message': event['message_id'], 'alarm': alarm.alarm_id})
        reason_data = {'type': 'event', 'event': event}
        self._refresh(alarm, state, reason, reason_data)

    def evaluate(self, alarm):
        pass
