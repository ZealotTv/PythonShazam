import hashlib
import numpy as np
import matplotlib.mlab as mlab
import matplotlib.pyplot as plt

from termcolor import colored
from scipy.ndimage.filters import maximum_filter
from scipy.ndimage.morphology import (generate_binary_structure, iterate_structure, binary_erosion)
from operator import itemgetter

IDX_FREQ_I = 0
IDX_TIME_J = 1

# Частота дискретизации, связанная с условиями Найквиста,
# которая влияет на частоты диапазона, которые мы можем обнаружить.
DEFAULT_FS = 44100

# Размер окна БПФ влияет на гранулярность частоты
DEFAULT_WINDOW_SIZE = 4096

# Отношение, при котором каждое последующее окно перекрывает последнее и следующее окно. 
# Более высокое перекрытие обеспечит более высокую степень детализации сопоставления смещения,
# но потенциально больше отпечатков пальцев.
DEFAULT_OVERLAP_RATIO = 0.5

# Степень, в которой отпечаток пальца может быть спарен со своими соседями --
# чем выше, тем больше отпечатков пальцев, но потенциально выше точность
DEFAULT_FAN_VALUE = 15

# Минимальная амплитуда в спектрограмме, чтобы считаться пиком.
# Это значение можно увеличить, чтобы уменьшить количество отпечатков пальцев,
# но это может отрицательно сказаться на точности.
DEFAULT_AMP_MIN = 10

# Количество ячеек вокруг амплитудного пика на спектрограмме, чтобы Дежавю считал его спектральным пиком.
# Более высокие значения означают меньше отпечатков пальцев и более быстрое сопоставление,
# но потенциально могут повлиять на точность.
PEAK_NEIGHBORHOOD_SIZE = 20

# Пороговые значения того, насколько близко или далеко могут быть отпечатки пальцев,
# чтобы их можно было связать с отпечатком пальца.
# Если максимальное значение слишком низкое, более высокие значения DEFAULT_FAN_VALUE могут не работать должным образом.
MIN_HASH_TIME_DELTA = 0
MAX_HASH_TIME_DELTA = 200

# Если True, пики будут сортироваться по времени для снятия отпечатков пальцев;
# отсутствие сортировки сократит количество отпечатков пальцев,
# но потенциально повлияет на производительность.
PEAK_SORT = True

# Количество битов, которые нужно отбросить с начала хэша SHA1 при вычислении отпечатка пальца. 
# Чем больше вы выбрасываете, тем меньше места для хранения, 
# но потенциально больше коллизий и неправильных классификаций при идентификации песен.
FINGERPRINT_REDUCTION = 20

def fingerprint(channel_samples, Fs=DEFAULT_FS,
                wsize=DEFAULT_WINDOW_SIZE,
                wratio=DEFAULT_OVERLAP_RATIO,
                fan_value=DEFAULT_FAN_VALUE,
                amp_min=DEFAULT_AMP_MIN,
                plots=False):

    # показать график спектрограммы
    if plots:
      plt.plot(channel_samples)
      plt.title('%d samples' % len(channel_samples))
      plt.xlabel('time (s)')
      plt.ylabel('amplitude (A)')
      plt.show()
      plt.gca().invert_yaxis()

    # БПФ канала, протоколировать выходные данные преобразования, находить локальные максимумы, 
    # а затем возвращать локально чувствительные хэши. 
    # БПФ сигнала и извлечения частотных составляющих

    # построить угловой спектр сегментов в сигнале в цветовой карте
    arr2D = mlab.specgram(
        channel_samples,
        NFFT=wsize,
        Fs=Fs,
        window=mlab.window_hanning,
        noverlap=int(wsize * wratio))[0]

    # показать график спектрограммы
    if plots:
      plt.plot(arr2D)
      plt.title('FFT')
      plt.show()

    # применить преобразование журнала, поскольку specgram() возвращает линейный массив
    arr2D = 10 * np.log10(arr2D) # вычислить логарифм по основанию 10 для всех элементов arr2D
    arr2D[arr2D == -np.inf] = 0  # заменить inf нулями

    # поиск локальных максимумов
    local_maxima = get_2D_peaks(arr2D, plot=plots, amp_min=amp_min)

    msg = '   local_maxima: %d of frequency & time pairs'
    local_maxima = list(local_maxima)
    print(colored(msg, attrs=['dark']) % len(local_maxima))

    # вернуть хэши
    return generate_hashes(local_maxima, fan_value=fan_value)

def get_2D_peaks(arr2D, plot=False, amp_min=DEFAULT_AMP_MIN):
    # http://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.morphology.iterate_structure.html#scipy.ndimage.morphology.iterate_structure
    struct = generate_binary_structure(2, 1)
    neighborhood = iterate_structure(struct, PEAK_NEIGHBORHOOD_SIZE)

    # найти локальные максимумы, используя форму фильтра
    local_max = maximum_filter(arr2D, footprint=neighborhood) == arr2D
    background = (arr2D == 0)
    eroded_background = binary_erosion(background, structure=neighborhood,
                                       border_value=1)

    # Булева маска arr2D с True на пиках
    detected_peaks = local_max ^ eroded_background

    # извлечение пиков
    amps = arr2D[detected_peaks]
    j, i = np.where(detected_peaks)

    # фильтрация пиков
    amps = amps.flatten()
    peaks = zip(i, j, amps)
    peaks_filtered = [x for x in peaks if x[2] > amp_min]  # freq, time, amp

    # получение индексов для частоты и времени
    frequency_idx = [x[1] for x in peaks_filtered]
    time_idx = [x[0] for x in peaks_filtered]

    # разброс пиков
    if plot:
      fig, ax = plt.subplots()
      ax.imshow(arr2D)
      ax.scatter(time_idx, frequency_idx)
      ax.set_xlabel('Time')
      ax.set_ylabel('Frequency')
      ax.set_title("Spectrogram")
      plt.gca().invert_yaxis()
      plt.show()

    return zip(frequency_idx, time_idx)

# Структура списка хешей: sha1_hash[0:20] time_offset
# пример: [(e05b341a9b77a51fd26, 32), ... ]
def generate_hashes(peaks, fan_value=DEFAULT_FAN_VALUE):
    if PEAK_SORT:
      peaks.sort(key=itemgetter(1))

    # перебор всех пиков
    for i in range(len(peaks)):
      for j in range(1, fan_value):
        if (i + j) < len(peaks):

          # взятие текущего и следующего значения пиковой частоты
          freq1 = peaks[i][IDX_FREQ_I]
          freq2 = peaks[i + j][IDX_FREQ_I]

          # принятие текущего и следующего смещения пикового времени
          t1 = peaks[i][IDX_TIME_J]
          t2 = peaks[i + j][IDX_TIME_J]

          # получение разницы временных смещений
          t_delta = t2 - t1

          # проверка, находится ли дельта между min и max
          if t_delta >= MIN_HASH_TIME_DELTA and t_delta <= MAX_HASH_TIME_DELTA:
            full_code = "%s|%s|%s" %(str(freq1), str(freq2), str(t_delta))
            h = hashlib.sha1(full_code.encode('utf-8'))
            yield (h.hexdigest()[0:FINGERPRINT_REDUCTION], t1)
