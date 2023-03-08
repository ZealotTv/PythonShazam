from .reader import BaseReader
import os
from pydub import AudioSegment
from pydub.utils import audioop
import numpy as np
from hashlib import sha1

class FileReader(BaseReader):
  def __init__(self, filename):
    self.filename = filename

  """
  Читает любой файл, поддерживаемый pydub (ffmpeg), и возвращает содержащиеся в нем данные. 
  Если чтение файла не удается из-за того, 
  что ввод является 24-битным wav-файлом, wavio используется в качестве резервной копии.

  При желании можно ограничить определенным количеством секунд от начала файла, 
  указав параметр `limit`. Это количество секунд от начала файла.

  возвращает: (каналы, частота дискретизации)
  """
  # pydub не поддерживает 24-битные файлы wav, в этом случае используйте wavio
  def parse_audio(self):
    limit = None

    songname, extension = os.path.splitext(os.path.basename(self.filename))

    try:
      audiofile = AudioSegment.from_file(self.filename)

      if limit:
        audiofile = audiofile[:limit * 1000]

      data = np.fromstring(audiofile._data, np.int16)

      channels = []
      for chn in range(audiofile.channels):
        channels.append(data[chn::audiofile.channels])

      fs = audiofile.frame_rate
    except audioop.error:
      print('audioop.error')
      pass

    return {
      "songname": songname,
      "extension": extension,
      "channels": channels,
      "Fs": audiofile.frame_rate,
      "file_hash": self.parse_file_hash()
    }

  def parse_file_hash(self, blocksize=2**20):
    """ Небольшая функция для генерации хэша для уникальной генерации файла.
     Вдохновленный версией MD5 здесь:
     http://stackoverflow.com/a/1131255/712997

    Работает с большими файлами.
    """
    s = sha1()

    with open(self.filename , "rb") as f:
      while True:
        buf = f.read(blocksize)
        if not buf: break
        s.update(buf)

    return s.hexdigest().upper()
