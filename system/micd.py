#!/usr/bin/env python3
import sounddevice as sd
import numpy as np

from cereal import messaging
from common.realtime import Ratekeeper
from system.hardware import HARDWARE
from system.swaglog import cloudlog


class Mic:
  def __init__(self, pm):
    self.pm = pm
    self.rk = Ratekeeper(1.0)
    self.noise_level = 0

  def update(self):
    msg = messaging.new_message('microphone')
    microphone = msg.microphone
    microphone.noiseLevel = float(self.noise_level)

    self.pm.send('microphone', msg)
    self.rk.keep_time()

  def calculate_volume(self, indata, frames, time, status):
    self.noise_level = np.linalg.norm(indata)

  def micd_thread(self, device=None):
    if device is None:
      device = HARDWARE.get_sound_input_device()

    with sd.InputStream(callback=self.calculate_volume, device=device) as stream:
      cloudlog.info(f"micd stream started: {stream.samplerate=} {stream.channels=} {stream.dtype=} {stream.device=}")
      while True:
        self.update()


def main(pm=None):
  if pm is None:
    pm = messaging.PubMaster(['microphone'])

  mic = Mic(pm)
  mic.micd_thread()


if __name__ == "__main__":
  main()
