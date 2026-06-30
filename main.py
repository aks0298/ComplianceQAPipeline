import uuid 
import json
import logging
from pprint import pprint

from dotenv import load_dotenv
load_dotenv(override=True)

from backend.src.graph.workflow import app

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

logger = logging.getLogger("ComplianceQAPipeline")

def run_cli_simulation():
    session_id=str(uuid.uuid4())
    logger.info(f"Starting CLI simulation with session ID: {session_id}")
    initial_inputs={
        "video_url":"https://youtu.be/Cyzz4tgLJXE",
        "video_id":f"video_{session_id[0:8]}",
        "compliance_results":[],
        "errors":[]
    }

    print("n------initial inputs------")

    print(json.dumps(initial_inputs, indent=4))

    try:
        final_state = app.invoke(initial_inputs)
        logger.info("Workflow completed successfully.")
        print("n------final state------")
        print(f"video id: {final_state.get('video_id')}")

        print(f"compliance results: {final_state.get('final_status')}")
        results=final_state.get('compliance_results', [])
        if results:
            for result in results:
                print("n------compliance result------")
                print(f"-[{result.get('severity')}] {result.get('category')}: {result.get('description')}")
        
        else:
            print("No violations found.")
        print("n------workflow completed------")
        print(f"Final state: {json.dumps(final_state, indent=4)}")
    except Exception as e:
        logger.error(f"Workflow failed: {str(e)}")
        print("n------error------")
        print(str(e))


if __name__ == "__main__":
    run_cli_simulation()
