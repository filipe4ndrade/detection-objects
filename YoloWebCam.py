import numpy as np
import cv2
import time
import pyttsx3
from csv import DictWriter
import threading
import queue

# URL do IP Webcam 
url = "http://192.168.0.105:8080/video"

# Defini qual câmera será utilizada na captura
camera = cv2.VideoCapture(0)

# Cria variáveis para captura de altura e largura
h, w = None, None

# Carrega o arquivo com o nome dos objetos que o modelo foi treinado para detectar
with open('yoloDados/YoloNames.names') as f:
    # Cria uma lista com todos os nomes
    labels = [line.strip() for line in f]

# Carrega os arquivos treinados pelo framework YOLO
network = cv2.dnn.readNetFromDarknet('yoloDados/yolov4-tiny.cfg', 'yoloDados/yolov4-tiny.weights')

# Captura uma lista com todos os nomes de objetos treinados pelo framework
layers_names_all = network.getLayerNames()

# Obtém apenas nomes de camadas de saída que precisamos do algoritmo YOLOv3
layers_names_output = [layers_names_all[i - 1] for i in network.getUnconnectedOutLayers()]

# Define probabilidade mínima para eliminar previsões fracas
probability_minimum = 0.5

# Define limite para filtrar caixas delimitadoras fracas com supressão não máxima
threshold = 0.3

# Gera cores aleatórias para as caixas de cada objeto detectado
colours = np.random.randint(0, 255, size=(len(labels), 3), dtype='uint8')

# Inicializa o mecanismo de síntese de fala
engine = pyttsx3.init()

# Dicionário para rastrear o tempo da última detecção de cada objeto
last_detection_time = {}

# Tempo mínimo (em segundos) entre as detecções do mesmo objeto
minimum_time_between_detections = 5.0

# Função para a thread de leitura de áudio
def audio_thread():
    engine = pyttsx3.init()
    while True:
        object_name = audio_queue.get()
        engine.say(f'{object_name}')
        engine.runAndWait()

# Inicializa a fila para comunicação entre as threads
audio_queue = queue.Queue()

# Inicia a thread de leitura de áudio
audio_thread = threading.Thread(target=audio_thread)
audio_thread.daemon = True
audio_thread.start()

# Resto do código é o mesmo

# Loop de captura e detecção dos objetos
with open('teste.csv', 'w') as arquivo:
    cabecalho = ['Detectado', 'Acuracia']
    escritor_csv = DictWriter(arquivo, fieldnames=cabecalho)
    escritor_csv.writeheader()
    while True:
        # Captura da câmera frame por frame
        _, frame = camera.read()

        if w is None or h is None:
            # Fatiar apenas dois primeiros elementos da tupla
            h, w = frame.shape[:2]

        # A forma resultante possui número de quadros, número de canais, largura e altura
        blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (416, 416), swapRB=True, crop=False)

        # Implementando o passe direto com nosso blob e somente através das camadas de saída
        network.setInput(blob)  # Definindo blob como entrada para a rede
        start = time.time()
        output_from_network = network.forward(layers_names_output)
        end = time.time()

        # Mostrando tempo gasto para um único quadro atual
        print('Tempo gasto atual {:.5f} segundos'.format(end - start))

        # Preparando listas para caixas delimitadoras detectadas
        bounding_boxes = []
        confidences = []
        class_numbers = []

        # Passando por todas as camadas de saída após o avanço da alimentação
        # Fase de detecção dos objetos
        for result in output_from_network:
            for detected_objects in result:
                scores = detected_objects[5:]
                class_current = np.argmax(scores)
                confidence_current = scores[class_current]

                # Eliminando previsões fracas com probabilidade mínima
                if confidence_current > probability_minimum:
                    box_current = detected_objects[0:4] * np.array([w, h, w, h])
                    x_center, y_center, box_width, box_height = box_current
                    x_min = int(x_center - (box_width / 2))
                    y_min = int(y_center - (box_height / 2))

                    # Adicionando resultados em listas preparadas
                    bounding_boxes.append([x_min, y_min, int(box_width), int(box_height)])
                    confidences.append(float(confidence_current))
                    class_numbers.append(class_current)

        results = cv2.dnn.NMSBoxes(bounding_boxes, confidences, probability_minimum, threshold)

        # Verificando se existe pelo menos um objeto detectado
        if len(results) > 0:
            for i in results.flatten():
                x_min, y_min = bounding_boxes[i][0], bounding_boxes[i][1]
                box_width, box_height = bounding_boxes[i][2], bounding_boxes[i][3]
                colour_box_current = colours[class_numbers[i]].tolist()
                cv2.rectangle(frame, (x_min, y_min), (x_min + box_width, y_min + box_height), colour_box_current, 2)

                # Preparando texto com rótulo e acurácia para o objeto detectado
                text_box_current = '{}: {:.4f}'.format(labels[int(class_numbers[i])], confidences[i])

                # Fale o nome do objeto detectado apenas se for diferente ou passaram 5 segundos
                object_name = text_box_current.split(':')[0]
                current_time = time.time()
                last_detection_time.setdefault(object_name, 0)
                if current_time - last_detection_time[object_name] >= minimum_time_between_detections:
                    audio_queue.put(object_name)  # Coloca o objeto na fila de áudio
                    last_detection_time[object_name] = current_time

                # Coloca o texto nos objetos detectados
                cv2.putText(frame, text_box_current, (x_min, y_min - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour_box_current, 2)

                escritor_csv.writerow({"Detectado": text_box_current.split(':')[0], "Acuracia": text_box_current.split(':')[1]})

                print(text_box_current.split(':')[0] + " - " + text_box_current.split(':')[1])

        cv2.namedWindow('YOLO v3 WebCamera', cv2.WINDOW_NORMAL)
        cv2.imshow('YOLO v3 WebCamera', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

camera.release()
cv2.destroyAllWindows()
