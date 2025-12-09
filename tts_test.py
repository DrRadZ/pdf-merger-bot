import pyttsx3
import platform

print("Python TTS test starting...")

system = platform.system()
print("Detected OS:", system)

# Try explicitly picking the driver per OS
if system == "Windows":
    engine = pyttsx3.init("sapi5")      # Windows speech API
elif system == "Darwin":                # macOS
    engine = pyttsx3.init("nsss")
else:                                   # Linux / others
    engine = pyttsx3.init("espeak")

voices = engine.getProperty("voices")
print("Available voices:")
for i, v in enumerate(voices):
    print(f"{i}: {v.id}")

engine.setProperty("rate", 160)

# You can change the index here to try different voices
if voices:
    engine.setProperty("voice", voices[0].id)

print("Saying: 'Hello, this is a test.'")
engine.say("Hello, this is a test.")
engine.runAndWait()

print("Done.")
