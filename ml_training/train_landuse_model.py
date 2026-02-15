# STEP 0: Import required libraries
import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv2D, MaxPooling2D, Flatten, Dense, Dropout
from tensorflow.keras.callbacks import ModelCheckpoint
import os

# STEP 1: Basic configuration
IMG_SIZE = 64          # image width & height
BATCH_SIZE = 32        # images processed at once
EPOCHS = 15            # how many times model sees data
DATASET_PATH = "../dataset"
MODEL_NAME = "best_model.h5"

# STEP 2: Load and prepare images
datagen = ImageDataGenerator(
    rescale=1.0 / 255,       # normalize pixels
    validation_split=0.2,    # 80% train, 20% validation
    rotation_range=15,
    horizontal_flip=True,
    zoom_range=0.1
)

train_data = datagen.flow_from_directory(
    DATASET_PATH,
    target_size=(IMG_SIZE, IMG_SIZE),
    batch_size=BATCH_SIZE,
    class_mode="categorical",
    subset="training"
)

val_data = datagen.flow_from_directory(
    DATASET_PATH,
    target_size=(IMG_SIZE, IMG_SIZE),
    batch_size=BATCH_SIZE,
    class_mode="categorical",
    subset="validation"
)

NUM_CLASSES = train_data.num_classes
print("Classes:", train_data.class_indices)

# STEP 3: Build CNN model
model = Sequential([
    Conv2D(32, (3, 3), activation="relu", input_shape=(IMG_SIZE, IMG_SIZE, 3)),
    MaxPooling2D(2, 2),

    Conv2D(64, (3, 3), activation="relu"),
    MaxPooling2D(2, 2),

    Conv2D(128, (3, 3), activation="relu"),
    MaxPooling2D(2, 2),

    Flatten(),
    Dense(256, activation="relu"),
    Dropout(0.5),
    Dense(NUM_CLASSES, activation="softmax")
])

# STEP 4: Compile model
model.compile(
    optimizer="adam",
    loss="categorical_crossentropy",
    metrics=["accuracy"]
)

model.summary()

# STEP 5: Save best model automatically
checkpoint = ModelCheckpoint(
    MODEL_NAME,
    monitor="val_accuracy",
    save_best_only=True,
    verbose=1
)

# STEP 6: Train the model
print("Training started...")
model.fit(
    train_data,
    validation_data=val_data,
    epochs=EPOCHS,
    callbacks=[checkpoint]
)

print("Training complete!")
print("Saved model:", MODEL_NAME)

# STEP 7: Final evaluation
loss, accuracy = model.evaluate(val_data)
print(f"Final validation accuracy: {accuracy * 100:.2f}%")
