import numpy as np
import tensorflow as tf
from tensorflow.keras.preprocessing.image import img_to_array, load_img
import os

# Load the trained model
MODEL_PATH = r"C:\Users\rushikesh chauhan\Desktop\MCA project final Year\New folder\models\face_recognition_model.h5"

try:
    model = tf.keras.models.load_model(MODEL_PATH)
    print("✅ Model loaded successfully!")
except Exception as e:
    print(f"❌ Error loading model: {e}")
    exit()

# Path to test image
TEST_IMAGE_PATH = r"C:\Users\rushikesh chauhan\Desktop\MCA project final Year\New folder\static\images\25MCA001.png"

if not os.path.exists(TEST_IMAGE_PATH):
    print("❌ Test image not found! Please provide a valid image.")
    exit()

# Load the test image
img = load_img(TEST_IMAGE_PATH, target_size=(100, 100), color_mode="grayscale")
img_array = img_to_array(img) / 255.0  # Normalize
img_array = np.expand_dims(img_array, axis=0)  # Add batch dimension

# Predict
predictions = model.predict(img_array)
predicted_label = np.argmax(predictions)  # Get class with highest probability

print(f"🎯 Predicted class: {predicted_label}")
