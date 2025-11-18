# app.py
from flask import Flask, jsonify, render_template, request
from data import get_metrics
import time

app = Flask(__name__)

# --- TUNING RULES (provider-specific) ---
def recommendations_for_aws(metrics):
    recs = []
    cpu = metrics.get('cpu', 0)
    mem = metrics.get('mem', 0)
    disk = metrics.get('disk', 0)
    net = metrics.get('network', 0)
    db_latency = metrics.get('db_latency', 0)
    req = metrics.get('requests', 0)

    # --- CPU ---
    if cpu > 90:
        recs.append("🔴 AWS: Critically high CPU — scale out Auto Scaling Group or upgrade EC2 instance family (C5/C6).")
    elif cpu > 75:
        recs.append("🟠 AWS: CPU elevated — enable CloudWatch alarms + ASG target tracking.")

    else:
        recs.append("🟢 AWS: CPU within normal operating range.")

    # --- Memory ---
    if mem > 85:
        recs.append("🔴 AWS: Memory pressure — move to R-series (memory optimized) EC2 or increase container memory limits.")
    elif mem > 65:
        recs.append("🟠 AWS: Moderate memory — inspect memory leaks via X-Ray or container profiling.")
    else:
        recs.append("🟢 AWS: Memory usage healthy.")

    # --- Disk ---
    if disk > 85:
        recs.append("🔴 AWS: Disk usage high — move from gp3 to io2, increase IOPS, or add EFS/EBS expansion.")
    elif disk > 60:
        recs.append("🟠 AWS: Disk moderately high — check for slow EBS volumes.")
    
    # --- Network ---
    if net > 80:
        recs.append("🔴 AWS: High network usage — consider ALB/NLB, enable caching (CloudFront), or use Global Accelerator.")
    elif net > 60:
        recs.append("🟠 AWS: Network traffic elevated — investigate noisy neighbor or unexpected traffic spikes.")

    # --- DB Latency (RDS) ---
    if db_latency > 250:
        recs.append("🔴 AWS RDS: Critical DB latency — add Read Replicas, increase instance class, or add Provisioned IOPS.")
    elif db_latency > 150:
        recs.append("🟠 AWS RDS: Latency warning — tune slow queries using Performance Insights.")

    # --- Request Load ---
    if req > 1500:
        recs.append("🔴 AWS: High request load — scale out ASG, enable caching with CloudFront, or add API Gateway throttling.")
    elif req > 900:
        recs.append("🟠 AWS: Requests increasing — consider adding ALB or reviewing application concurrency.")

    # --- Combined Conditions ---
    if cpu > 80 and req > 1200:
        recs.append("🔴 AWS: CPU + traffic spike — apply target tracking autoscaling and enable Auto Scaling warm pools.")

    if mem > 80 and db_latency > 200:
        recs.append("🔴 AWS: Memory + DB latency — indicates DB connection saturation. Check connection pool settings.")

    return recs


def recommendations_for_azure(metrics):
    recs = []
    cpu = metrics.get('cpu', 0)
    mem = metrics.get('mem', 0)
    disk = metrics.get('disk', 0)
    net = metrics.get('network', 0)
    req_rate = metrics.get('request_rate', 0)
    fail = metrics.get('failure_rate', 0)

    # CPU
    if cpu > 90:
        recs.append("🔴 Azure: CPU maxed — scale up App Service Plan (P1V3/P2V3) or use VMSS autoscale.")
    elif cpu > 70:
        recs.append("🟠 Azure: High CPU — enable autoscale rules based on % CPU + request count.")
    else:
        recs.append("🟢 Azure: CPU normal.")

    # Memory
    if mem > 85:
        recs.append("🔴 Azure: Memory high — increase service plan tier or check memory leaks with Application Insights Profiler.")
    elif mem > 60:
        recs.append("🟠 Azure: Moderate memory — validate app recycle interval, container memory limits.")

    # Disk
    if disk > 85:
        recs.append("🔴 Azure: Disk pressure — upgrade to Premium SSD or Ultra Disk.")
    elif disk > 60:
        recs.append("🟠 Azure: Disk moderately high — check IOPS throttling.")

    # Network
    if net > 80:
        recs.append("🔴 Azure: High network load — add Azure Front Door or Traffic Manager.")
    elif net > 60:
        recs.append("🟠 Azure: Elevated network — enable CDN caching.")

    # Request Rate
    if req_rate > 350:
        recs.append("🔴 Azure: Heavy request rate — enable autoscale rules using App Service scale-out.")
    elif req_rate > 200:
        recs.append("🟠 Azure: Increasing request rate — configure Azure API Management caching.")

    # Failure Rate
    if fail > 4:
        recs.append("🔴 Azure: High failure rate — examine Application Insights traces for 5xx errors.")
    elif fail > 2:
        recs.append("🟠 Azure: Noticeable failures — check dependency availability.")

    # Combined Conditions
    if cpu > 80 and req_rate > 300:
        recs.append("🔴 Azure: CPU + load spike — configure scale rules with CPU & HTTP queue length.")

    if mem > 80 and fail > 3:
        recs.append("🔴 Azure: Memory + failures — likely thread exhaustion or memory leak.")

    return recs


def recommendations_for_gcp(metrics):
    recs = []
    cpu = metrics.get('cpu', 0)
    mem = metrics.get('mem', 0)
    disk = metrics.get('disk', 0)
    net = metrics.get('network', 0)
    qps = metrics.get('qps', 0)
    latency = metrics.get('latency', 0)

    # CPU
    if cpu > 90:
        recs.append("🔴 GCP: CPU saturated — scale MIG (Managed Instance Groups) or move to C2/C3 machine types.")
    elif cpu > 70:
        recs.append("🟠 GCP: High CPU — analyze hot paths with Cloud Profiler.")
    else:
        recs.append("🟢 GCP: CPU healthy.")

    # Memory
    if mem > 85:
        recs.append("🔴 GCP: Memory at limit — switch to memory-optimized (M2/M3) instances.")
    elif mem > 60:
        recs.append("🟠 GCP: Memory rising — check container memory and GKE HPA/VPA policies.")

    # Disk
    if disk > 85:
        recs.append("🔴 GCP: Disk heavy — upgrade Persistent Disk to SSD or increase I/O limits.")
    elif disk > 60:
        recs.append("🟠 GCP: Disk moderate — examine slow queries or log spikes.")

    # Network
    if net > 80:
        recs.append("🔴 GCP: Network congestion — use Cloud CDN, global load balancing.")
    elif net > 60:
        recs.append("🟠 GCP: Elevated network — investigate large egress patterns.")

    # Latency
    if latency > 250:
        recs.append("🔴 GCP: Critical latency — use Cloud Tasks, Memorystore caching, or split microservices.")
    elif latency > 120:
        recs.append("🟠 GCP: Latency high — tune database or add regional replicas.")

    # QPS
    if qps > 2500:
        recs.append("🔴 GCP: Very high QPS — scale MIG + enable Global Load Balancer.")
    elif qps > 1400:
        recs.append("🟠 GCP: QPS rising — increase minimum instances.")

    # Combined Conditions
    if qps > 2000 and latency > 200:
        recs.append("🔴 GCP: QPS + latency spike — enable autoscaling based on request count & latency.")

    return recs


def provider_recommendations(provider, metrics):
    p = provider.lower()
    if p == "aws":
        return recommendations_for_aws(metrics)
    if p == "azure":
        return recommendations_for_azure(metrics)
    if p == "gcp":
        return recommendations_for_gcp(metrics)
    return ["Invalid provider"]


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/metrics")
def metrics_route():
    provider = request.args.get("provider", "aws")
    data = get_metrics(provider)
    recs = provider_recommendations(provider, data)
    data["recommendations"] = recs

    status = "normal"
    for r in recs:
        if r.startswith("🔴"): status = "critical"; break
        if r.startswith("🟠") and status != "critical": status = "warning"

    data["status"] = status
    return jsonify(data)


@app.route("/manual", methods=["POST"])
def manual():
    payload = request.get_json() or {}
    provider = payload.get("provider", "aws")

    metrics = {
        "cpu": float(payload.get("cpu", 0)),
        "mem": float(payload.get("mem", 0)),
        "disk": float(payload.get("disk", 0)),
        "network": float(payload.get("network", 0)),
        "db_latency": float(payload.get("db_latency", 0)),
        "requests": int(payload.get("requests", 0)),
        "request_rate": float(payload.get("request_rate", 0)),
        "failure_rate": float(payload.get("failure_rate", 0)),
        "qps": int(payload.get("qps", 0)),
        "latency": float(payload.get("latency", 0))
    }

    recs = provider_recommendations(provider, metrics)

    status = "normal"
    for r in recs:
        if r.startswith("🔴"): status = "critical"; break
        if r.startswith("🟠") and status != "critical": status = "warning"

    return jsonify({"metrics": metrics, "recommendations": recs, "status": status})


@app.route("/ping")
def ping():
    return jsonify({"ok": True, "ts": int(time.time())})


if __name__ == "__main__":
    app.run(debug=False)