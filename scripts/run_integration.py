import subprocess
import time
import json
import urllib.request
import urllib.error
import asyncio
from pathlib import Path

# Need a simple SSE client
async def fetch_sse(url):
    import aiohttp
    events = []
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            async for line in response.content:
                if line:
                    events.append(line.decode('utf-8').strip())
    return events

def run_integration():
    Path("results/Frontend-API-Integration/reports").mkdir(parents=True, exist_ok=True)
    report_file = Path("results/Frontend-API-Integration/reports/report.md")
    
    server = subprocess.Popen(["python", "-m", "uvicorn", "frontend.api.app:app", "--host", "127.0.0.1", "--port", "8000"])
    
    # Wait for server to start
    time.sleep(3)
    
    report = ["# Frontend-API Integration Smoke Test Report\n\n"]
    
    try:
        # 1. Health check
        req = urllib.request.Request("http://127.0.0.1:8000/api/health")
        with urllib.request.urlopen(req) as response:
            health = json.loads(response.read())
            report.append(f"## Health Check\n```json\n{json.dumps(health, indent=2)}\n```\n")
            
        # 2. Capabilities
        req = urllib.request.Request("http://127.0.0.1:8000/api/capabilities")
        with urllib.request.urlopen(req) as response:
            caps = json.loads(response.read())
            report.append(f"## Capabilities\n```json\n{json.dumps(caps, indent=2)}\n```\n")
            
        import aiohttp
        async def run_scenario(scenario_name, input_text, device):
            report.append(f"## Scenario: {scenario_name}\n")
            data = json.dumps({"input": input_text, "compression_device": device}).encode("utf-8")
            req = urllib.request.Request("http://127.0.0.1:8000/api/compare", data=data, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req) as response:
                    job_res = json.loads(response.read())
                    job_id = job_res["job_id"]
                    report.append(f"Job created: {job_id}\n")
            except Exception as e:
                report.append(f"Job creation failed: {e}\n")
                return
                
            events = await fetch_sse(f"http://127.0.0.1:8000/api/compare/{job_id}/events")
            report.append("### SSE Events\n```\n")
            for evt in events:
                report.append(evt + "\n")
            report.append("```\n")
            
        async def main_async():
            # Scenario 1: Question-only comparison
            await run_scenario("Question-only", "What is the meaning of life?", "cpu")
            
            # Scenario 2: Context + question CPU
            await run_scenario("Context + question CPU", "The meaning of life is 42.\n\nWhat is the meaning of life?", "cpu")
            
            if caps.get("cuda_available"):
                # Scenario 3: Context + question GPU
                await run_scenario("Context + question GPU", "The meaning of life is 42.\n\nWhat is the meaning of life?", "cuda")
                
        asyncio.run(main_async())
        
    finally:
        server.terminate()
        server.wait()
        
    with open(report_file, "w") as f:
        f.writelines(report)
        
    print("Integration tests finished. Report written to", report_file)

if __name__ == "__main__":
    run_integration()
