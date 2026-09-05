import time
from gliner import GLiNER

print("Loading GLiNER Medium v2.1...")

start = time.perf_counter()

model = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")

load_time = time.perf_counter() - start

print(f"Model loaded in {load_time:.2f} seconds")

text = """
John operates a Telegram channel called DarkMarket where customers
can purchase heroin and tramadol. Payments are accepted in Bitcoin.
The vendor offers 100 tablets for $80 and can be contacted at
+91 9876543210.
"""

labels = [
    "person",
    "drug",
    "vendor",
    "marketplace",
    "messaging platform",
    "cryptocurrency",
    "phone number",
    "drug quantity",
    "drug price",
]

print("\nRunning extraction...")

start = time.perf_counter()

entities = model.predict_entities(
    text,
    labels,
    threshold=0.5,
)

inference_time = time.perf_counter() - start

print(f"Inference time: {inference_time:.2f} seconds")

print("\nEntities:")
for entity in entities:
    print(
        f"{entity['text']} → "
        f"{entity['label']} "
        f"(score={entity['score']:.3f})"
    )