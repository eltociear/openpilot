#!/usr/bin/env python3
import time

import sounddevice as sd
import numpy as np

from cereal import messaging
from common.filter_simple import FirstOrderFilter
from common.realtime import Ratekeeper
from system.hardware import HARDWARE
from system.swaglog import cloudlog

DT_MIC = 0.1

SAMPLERATE = 44100

MUTE_TIME = 5


class Mic:
  def __init__(self, pm, sm):
    self.pm = pm
    self.sm = sm
    self.rk = Ratekeeper(DT_MIC)

    self.measurements = np.array([])
    self.filter = FirstOrderFilter(0, 10, DT_MIC, initialized=False)
    self.last_alert_time = 0

  @property
  def noise_level(self):
    return self.filter.x

  @property
  def muted(self):
    return time.time() - self.last_alert_time < MUTE_TIME

  def update(self):
    if self.sm.updated['controlsState']:
      if self.sm['controlsState'].alertSound > 0:
        self.last_alert_time = time.time()

    if len(self.measurements) >= SAMPLERATE:
      self.filter.update(float(np.linalg.norm(self.measurements)))
      self.measurements = np.array([])

    msg = messaging.new_message('microphone')
    microphone = msg.microphone
    microphone.noiseLevel = self.noise_level

    self.pm.send('microphone', msg)
    self.rk.keep_time()

  def callback(self, indata, frames, time, status):
    if not self.muted:
      self.measurements = np.concatenate((self.measurements, indata[:, 0]))

  def micd_thread(self, device=None):
    if device is None:
      device = HARDWARE.get_sound_input_device()

    with sd.InputStream(device=device, channels=1, samplerate=SAMPLERATE, callback=self.callback) as stream:
      cloudlog.info(f"micd stream started: {stream.samplerate=} {stream.channels=} {stream.dtype=} {stream.device=}")
      while True:
        self.update()


def main(pm=None, sm=None):
  if pm is None:
    pm = messaging.PubMaster(['microphone'])
  if sm is None:
    sm = messaging.SubMaster(['controlsState'])

  mic = Mic(pm, sm)
  mic.micd_thread()


if __name__ == "__main__":
  main()
