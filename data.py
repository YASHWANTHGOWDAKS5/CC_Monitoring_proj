# improved_dummy_data.py
import random
import time

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

class MetricGenerator:
    def __init__(self):
        self.prev = {"aws": {}, "azure": {}, "gcp": {}}

    def drift(self, prev, step, lo, hi):
        """Smooth random drift with boundaries."""
        if prev is None:
            return round(random.uniform(lo + 5, hi - 5), 1)

        change = random.uniform(-step, step)
        return round(clamp(prev + change, lo, hi), 1)

    def incident_spike(self, prob=0.05, magnitude=40):
        """Small chance of a large spike."""
        if random.random() < prob:
            return random.uniform(10, magnitude)
        return 0

    def generate(self, provider):
        p = provider.lower()
        s = self.prev[p]

        # --- Base metrics ---
        cpu = self.drift(s.get("cpu"), step=6, lo=5, hi=98)
        mem = self.drift(s.get("mem"), step=5, lo=5, hi=95)
        disk = self.drift(s.get("disk"), step=4, lo=5, hi=95)
        net = self.drift(s.get("network"), step=5, lo=3, hi=95)

        # Add incident event spikes (random real-world bursts)
        cpu = clamp(cpu + self.incident_spike(), 0, 90)
        mem = clamp(mem + self.incident_spike(prob=0.03), 0, 80)
        net = clamp(net + self.incident_spike(prob=0.04), 0, 100)

        # Slight correlation for realism
        if cpu > 80:
            mem += random.uniform(2, 6)
            disk += random.uniform(1, 4)

        # --- Provider-specific metrics ---
        if p == "aws":
            db = self.drift(s.get("db_latency"), step=12, lo=15, hi=380)
            req = int(self.drift(s.get("requests"), step=180, lo=80, hi=2400))

            # AWS behavior patterns
            if req > 2000:
                db += random.uniform(10, 40)
                cpu += random.uniform(3, 8)

            s.update(cpu=cpu, mem=mem, disk=disk, network=net,
                     db_latency=db, requests=req)

        elif p == "azure":
            rr = self.drift(s.get("request_rate"), step=35, lo=10, hi=520)
            fr = round(self.drift(s.get("failure_rate"), step=1.2, lo=0, hi=12), 2)

            # Azure patterns
            if rr > 400:
                fr += random.uniform(0.5, 2)
                cpu += random.uniform(4, 8)

            s.update(cpu=cpu, mem=mem, disk=disk, network=net,
                     request_rate=rr, failure_rate=fr)

        else:  # GCP
            qps = int(self.drift(s.get("qps"), step=250, lo=20, hi=3500))
            lat = self.drift(s.get("latency"), step=15, lo=5, hi=480)

            # GCP patterns
            if qps > 2500:
                lat += random.uniform(15, 50)
                cpu += random.uniform(2, 7)

            s.update(cpu=cpu, mem=mem, disk=disk, network=net,
                     qps=qps, latency=lat)

        # --- Finalize snapshot ---
        snap = dict(s)
        snap["cpu"] = clamp(snap["cpu"], 0, 100)
        snap["mem"] = clamp(snap["mem"], 0, 100)
        snap["disk"] = clamp(snap["disk"], 0, 100)
        snap["network"] = clamp(snap["network"], 0, 100)

        snap["timestamp"] = int(time.time())
        snap["provider"] = p
        return snap

gen = MetricGenerator()

def get_metrics(provider="aws"):
    if provider not in ["aws", "azure", "gcp"]:
        provider = "aws"
    return gen.generate(provider)
