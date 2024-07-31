# from .util import get_app_root
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from alembic import command, util
from alembic.config import Config
from loguru import logger

# from ..utils.db_utils import get_db_uri
from sqlmodel import Session, create_engine, text

from autogen.agentchat import AssistantAgent

from ..datamodel import (
    Agent,
    AgentConfig,
    AgentType,
    CodeExecutionConfigTypes,
    Criteria,
    Model,
    Skill,
    Workflow,
    WorkflowAgentLink,
    WorkFlowType,
)


def workflow_from_id(workflow_id: int, dbmanager: Any):
    workflow = dbmanager.get(Workflow, filters={"id": workflow_id}).data
    if not workflow or len(workflow) == 0:
        raise ValueError("The specified workflow does not exist.")
    workflow = workflow[0].model_dump(mode="json")
    workflow_agent_links = dbmanager.get(WorkflowAgentLink, filters={"workflow_id": workflow_id}).data

    def dump_agent(agent: Agent):
        exclude = []
        if agent.type != AgentType.groupchat:
            exclude = [
                "admin_name",
                "messages",
                "max_round",
                "admin_name",
                "speaker_selection_method",
                "allow_repeat_speaker",
            ]
        return agent.model_dump(warnings=False, mode="json", exclude=exclude)

    def get_agent(agent_id):
        with Session(dbmanager.engine) as session:
            agent: Agent = dbmanager.get_items(Agent, filters={"id": agent_id}, session=session).data[0]
            agent_dict = dump_agent(agent)
            agent_dict["skills"] = [Skill.model_validate(skill.model_dump(mode="json")) for skill in agent.skills]
            model_exclude = [
                "id",
                "agent_id",
                "created_at",
                "updated_at",
                "user_id",
                "description",
            ]
            models = [model.model_dump(mode="json", exclude=model_exclude) for model in agent.models]
            agent_dict["models"] = [model.model_dump(mode="json") for model in agent.models]

            if len(models) > 0:
                agent_dict["config"]["llm_config"] = agent_dict.get("config", {}).get("llm_config", {})
                llm_config = agent_dict["config"]["llm_config"]
                if llm_config:
                    llm_config["config_list"] = models
                agent_dict["config"]["llm_config"] = llm_config
            agent_dict["agents"] = [get_agent(agent.id) for agent in agent.agents]
            return agent_dict

    agents = []
    for link in workflow_agent_links:
        agent_dict = get_agent(link.agent_id)
        agents.append({"agent": agent_dict, "link": link.model_dump(mode="json")})
        # workflow[str(link.agent_type.value)] = agent_dict
    if workflow["type"] == WorkFlowType.sequential.value:
        # sort agents by sequence_id in link
        agents = sorted(agents, key=lambda x: x["link"]["sequence_id"])
    workflow["agents"] = agents
    return workflow


def run_migration(engine_uri: str):
    database_dir = Path(__file__).parent
    script_location = database_dir / "migrations"

    engine = create_engine(engine_uri)
    buffer = open(script_location / "alembic.log", "w")
    alembic_cfg = Config(stdout=buffer)
    alembic_cfg.set_main_option("script_location", str(script_location))
    alembic_cfg.set_main_option("sqlalchemy.url", engine_uri)

    print(f"Running migrations with engine_uri: {engine_uri}")

    should_initialize_alembic = False
    with Session(engine) as session:
        try:
            session.exec(text("SELECT * FROM alembic_version"))
        except Exception:
            logger.info("Alembic not initialized")
            should_initialize_alembic = True
        else:
            logger.info("Alembic already initialized")

    if should_initialize_alembic:
        try:
            logger.info("Initializing alembic")
            command.ensure_version(alembic_cfg)
            command.upgrade(alembic_cfg, "head")
            logger.info("Alembic initialized")
        except Exception as exc:
            logger.error(f"Error initializing alembic: {exc}")
            raise RuntimeError("Error initializing alembic") from exc

    logger.info(f"Running DB migrations in {script_location}")

    try:
        buffer.write(f"{datetime.now().isoformat()}: Checking migrations\n")
        command.check(alembic_cfg)
    except Exception as exc:
        if isinstance(exc, (util.exc.CommandError, util.exc.AutogenerateDiffsDetected)):
            try:
                command.upgrade(alembic_cfg, "head")
                time.sleep(3)
            except Exception as exc:
                logger.error(f"Error running migrations: {exc}")

    try:
        buffer.write(f"{datetime.now().isoformat()}: Checking migrations\n")
        command.check(alembic_cfg)
    except util.exc.AutogenerateDiffsDetected as exc:
        logger.info(f"AutogenerateDiffsDetected: {exc}")
        # raise RuntimeError(
        #     f"There's a mismatch between the models and the database.\n{exc}")
    except util.exc.CommandError as exc:
        logger.error(f"CommandError: {exc}")
        # raise RuntimeError(f"Error running migrations: {exc}")


def init_db_samples(dbmanager: Any):
    workflows = dbmanager.get(Workflow).data
    workflow_names = [w.name for w in workflows]
    if "Default Workflow" in workflow_names and "Travel Planning Workflow" in workflow_names:
        logger.info("Database already initialized with Default and Travel Planning Workflows")
        return
    logger.info("Initializing database with Default and Travel Planning Workflows")

    # models
    google_gemini_model = Model(
        model="gemini-1.5-pro-latest",
        description="Google's Gemini model",
        user_id="guestuser@gmail.com",
        api_type="google",
    )
    azure_model = Model(
        model="gpt4-turbo",
        description="Azure OpenAI  model",
        user_id="guestuser@gmail.com",
        api_type="azure",
        base_url="https://api.your azureendpoint.com/v1",
    )
    zephyr_model = Model(
        model="zephyr",
        description="Local Huggingface Zephyr model via vLLM, LMStudio or Ollama",
        base_url="http://localhost:1234/v1",
        user_id="guestuser@gmail.com",
        api_type="open_ai",
    )

    gpt_4_model = Model(
        model="gpt-4-1106-preview", description="OpenAI GPT-4 model", user_id="guestuser@gmail.com", api_type="open_ai"
    )

    # skills
    generate_pdf_skill = Skill(
        name="generate_and_save_pdf",
        description="Generate and save a pdf file based on the provided input sections.",
        user_id="guestuser@gmail.com",
        libraries=["requests", "fpdf", "PIL"],
        content='import uuid\nimport requests\nfrom fpdf import FPDF\nfrom typing import List, Dict, Optional\nfrom pathlib import Path\nfrom PIL import Image, ImageDraw, ImageOps\nfrom io import BytesIO\n\ndef generate_and_save_pdf(\n    sections: List[Dict[str, Optional[str]]], \n    output_file: str = "report.pdf", \n    report_title: str = "PDF Report"\n) -> None:\n    """\n    Function to generate a beautiful PDF report in A4 paper format. \n\n    :param sections: A list of sections where each section is represented by a dictionary containing:\n                     - title: The title of the section.\n                     - level: The heading level (e.g., "title", "h1", "h2").\n                     - content: The content or body text of the section.\n                     - image: (Optional) The URL or local path to the image.\n    :param output_file: The name of the output PDF file. (default is "report.pdf")\n    :param report_title: The title of the report. (default is "PDF Report")\n    :return: None\n    """\n\n    def get_image(image_url_or_path):\n        if image_url_or_path.startswith("http://") or image_url_or_path.startswith("https://"):\n            response = requests.get(image_url_or_path)\n            if response.status_code == 200:\n                return BytesIO(response.content)\n        elif Path(image_url_or_path).is_file():\n            return open(image_url_or_path, \'rb\')\n        return None\n\n    def add_rounded_corners(img, radius=6):\n        mask = Image.new(\'L\', img.size, 0)\n        draw = ImageDraw.Draw(mask)\n        draw.rounded_rectangle([(0, 0), img.size], radius, fill=255)\n        img = ImageOps.fit(img, mask.size, centering=(0.5, 0.5))\n        img.putalpha(mask)\n        return img\n\n    class PDF(FPDF):\n        def header(self):\n            self.set_font("Arial", "B", 12)\n            self.cell(0, 10, report_title, 0, 1, "C")\n            \n        def chapter_title(self, txt): \n            self.set_font("Arial", "B", 12)\n            self.cell(0, 10, txt, 0, 1, "L")\n            self.ln(2)\n        \n        def chapter_body(self, body):\n            self.set_font("Arial", "", 12)\n            self.multi_cell(0, 10, body)\n            self.ln()\n\n        def add_image(self, img_data):\n            img = Image.open(img_data)\n            img = add_rounded_corners(img)\n            img_path = Path(f"temp_{uuid.uuid4().hex}.png")\n            img.save(img_path, format="PNG")\n            self.image(str(img_path), x=None, y=None, w=190 if img.width > 190 else img.width)\n            self.ln(10)\n            img_path.unlink()\n\n    pdf = PDF()\n    pdf.add_page()\n    font_size = {"title": 16, "h1": 14, "h2": 12, "body": 12}\n\n    for section in sections:\n        title, level, content, image = section.get("title", ""), section.get("level", "h1"), section.get("content", ""), section.get("image")\n        pdf.set_font("Arial", "B" if level in font_size else "", font_size.get(level, font_size["body"]))\n        pdf.chapter_title(title)\n\n        if content: pdf.chapter_body(content)\n        if image:\n            img_data = get_image(image)\n            if img_data:\n                pdf.add_image(img_data)\n                if isinstance(img_data, BytesIO):\n                    img_data.close()\n\n    pdf.output(output_file)\n    print(f"PDF report saved as {output_file}")\n\n# # Example usage\n# sections = [\n#     {\n#         "title": "Introduction - Early Life",\n#         "level": "h1",\n#         "image": "https://picsum.photos/536/354",\n#         "content": ("Marie Curie was born on 7 November 1867 in Warsaw, Poland. "\n#                     "She was the youngest of five children. Both of her parents were teachers. "\n#                     "Her father was a math and physics instructor, and her mother was the head of a private school. "\n#                     "Marie\'s curiosity and brilliance were evident from an early age."),\n#     },\n#     {\n#         "title": "Academic Accomplishments",\n#         "level": "h2",\n#         "content": ("Despite many obstacles, Marie Curie earned degrees in physics and mathematics from the University of Paris. "\n#                     "She conducted groundbreaking research on radioactivity, becoming the first woman to win a Nobel Prize. "\n#                     "Her achievements paved the way for future generations of scientists, particularly women in STEM fields."),\n#     },\n#     {\n#         "title": "Major Discoveries",\n#         "level": "h2",\n#         "image": "https://picsum.photos/536/354",\n#         "content": ("One of Marie Curie\'s most notable discoveries was that of radium and polonium, two radioactive elements. "\n#                     "Her meticulous work not only advanced scientific understanding but also had practical applications in medicine and industry."),\n#     },\n#     {\n#         "title": "Conclusion - Legacy",\n#         "level": "h1",\n#         "content": ("Marie Curie\'s legacy lives on through her contributions to science, her role as a trailblazer for women in STEM, "\n#                     "and the ongoing impact of her discoveries on modern medicine and technology. "\n#                     "Her life and work remain an inspiration to many, demonstrating the power of perseverance and intellectual curiosity."),\n#     },\n# ]\n\n# generate_and_save_pdf_report(sections, "my_report.pdf", "The Life of Marie Curie")',
    )
    generate_image_skill = Skill(
        name="generate_and_save_images",
        secrets=[{"secret": "OPENAI_API_KEY", "value": None}],
        libraries=["openai"],
        description="Generate and save images based on a user's query.",
        content='\nfrom typing import List\nimport uuid\nimport requests  # to perform HTTP requests\nfrom pathlib import Path\n\nfrom openai import OpenAI\n\n\ndef generate_and_save_images(query: str, image_size: str = "1024x1024") -> List[str]:\n    """\n    Function to paint, draw or illustrate images based on the users query or request. Generates images from a given query using OpenAI\'s DALL-E model and saves them to disk.  Use the code below anytime there is a request to create an image.\n\n    :param query: A natural language description of the image to be generated.\n    :param image_size: The size of the image to be generated. (default is "1024x1024")\n    :return: A list of filenames for the saved images.\n    """\n\n    client = OpenAI()  # Initialize the OpenAI client\n    response = client.images.generate(model="dall-e-3", prompt=query, n=1, size=image_size)  # Generate images\n\n    # List to store the file names of saved images\n    saved_files = []\n\n    # Check if the response is successful\n    if response.data:\n        for image_data in response.data:\n            # Generate a random UUID as the file name\n            file_name = str(uuid.uuid4()) + ".png"  # Assuming the image is a PNG\n            file_path = Path(file_name)\n\n            img_url = image_data.url\n            img_response = requests.get(img_url)\n            if img_response.status_code == 200:\n                # Write the binary content to a file\n                with open(file_path, "wb") as img_file:\n                    img_file.write(img_response.content)\n                    print(f"Image saved to {file_path}")\n                    saved_files.append(str(file_path))\n            else:\n                print(f"Failed to download the image from {img_url}")\n    else:\n        print("No image data found in the response!")\n\n    # Return the list of saved files\n    return saved_files\n\n\n# Example usage of the function:\n# generate_and_save_images("A cute baby sea otter")\n',
        user_id="guestuser@gmail.com",
    )

    # agents

    planner_assistant_config = AgentConfig(
        name="planner_assistant",
        description="Assistant Agent",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=25,
        system_message="You are a helpful assistant that can suggest a travel plan for a user and utilize any context information provided. You are the primary cordinator who will receive suggestions or advice from other agents (local_assistant, language_assistant). You must ensure that the finally plan integrates the suggestions from other agents or team members. YOUR FINAL RESPONSE MUST BE THE COMPLETE PLAN. When the plan is complete and all perspectives are integrated, you can respond with TERMINATE.",
        code_execution_config=CodeExecutionConfigTypes.none,
        llm_config={},
    )
    planner_assistant = Agent(
        user_id="guestuser@gmail.com",
        type=AgentType.assistant,
        config=planner_assistant_config.model_dump(mode="json"),
    )

    local_assistant_config = AgentConfig(
        name="local_assistant",
        description="Local Assistant Agent",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=25,
        system_message="You are a local assistant that can suggest local activities or places to visit for a user and can utilize any context information provided. You can suggest local activities, places to visit, restaurants to eat at, etc. You can also provide information about the weather, local events, etc. You can provide information about the local area, but you cannot suggest a complete travel plan. You can only provide information about the local area.",
        code_execution_config=CodeExecutionConfigTypes.none,
        llm_config={},
    )
    local_assistant = Agent(
        user_id="guestuser@gmail.com", type=AgentType.assistant, config=local_assistant_config.model_dump(mode="json")
    )

    language_assistant_config = AgentConfig(
        name="language_assistant",
        description="Language Assistant Agent",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=25,
        system_message="You are a helpful assistant that can review travel plans, providing feedback on important/critical tips about how best to address language or communication challenges for the given destination. If the plan already includes language tips, you can mention that the plan is satisfactory, with rationale.",
        code_execution_config=CodeExecutionConfigTypes.none,
        llm_config={},
    )
    language_assistant = Agent(
        user_id="guestuser@gmail.com",
        type=AgentType.assistant,
        config=language_assistant_config.model_dump(mode="json"),
    )

    # group chat agent
    travel_groupchat_config = AgentConfig(
        name="travel_groupchat",
        admin_name="groupchat",
        description="Group Chat Agent Configuration",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=25,
        system_message="You are a group chat manager",
        code_execution_config=CodeExecutionConfigTypes.none,
        default_auto_reply="TERMINATE",
        llm_config={},
        speaker_selection_method="auto",
    )
    travel_groupchat_agent = Agent(
        user_id="guestuser@gmail.com", type=AgentType.groupchat, config=travel_groupchat_config.model_dump(mode="json")
    )

    user_proxy_config = AgentConfig(
        name="user_proxy",
        description="User Proxy Agent Configuration",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=25,
        system_message="You are a helpful assistant",
        code_execution_config=CodeExecutionConfigTypes.local,
        default_auto_reply="TERMINATE",
        llm_config=False,
    )
    user_proxy = Agent(
        user_id="guestuser@gmail.com", type=AgentType.userproxy, config=user_proxy_config.model_dump(mode="json")
    )

    default_assistant_config = AgentConfig(
        name="default_assistant",
        description="Assistant Agent",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=25,
        system_message=AssistantAgent.DEFAULT_SYSTEM_MESSAGE,
        code_execution_config=CodeExecutionConfigTypes.none,
        llm_config={},
    )
    default_assistant = Agent(
        user_id="guestuser@gmail.com", type=AgentType.assistant, config=default_assistant_config.model_dump(mode="json")
    )

    # workflows
    travel_workflow = Workflow(
        name="Travel Planning Workflow",
        description="Travel workflow",
        user_id="guestuser@gmail.com",
        sample_tasks=["Plan a 3 day trip to Hawaii Islands.", "Plan an eventful and exciting trip to  Uzbeksitan."],
    )
    default_workflow = Workflow(
        name="Default Workflow",
        description="Default workflow",
        user_id="guestuser@gmail.com",
        sample_tasks=[
            "paint a picture of a glass of ethiopian coffee, freshly brewed in a tall glass cup, on a table right in front of a lush green forest scenery",
            "Plot the stock price of NVIDIA YTD.",
        ],
    )

    with Session(dbmanager.engine) as session:
        session.add(zephyr_model)
        session.add(google_gemini_model)
        session.add(azure_model)
        session.add(gpt_4_model)
        session.add(generate_image_skill)
        session.add(generate_pdf_skill)
        session.add(user_proxy)
        session.add(default_assistant)
        session.add(travel_groupchat_agent)
        session.add(planner_assistant)
        session.add(local_assistant)
        session.add(language_assistant)

        session.add(travel_workflow)
        session.add(default_workflow)
        session.commit()

        dbmanager.link(link_type="agent_model", primary_id=default_assistant.id, secondary_id=gpt_4_model.id)
        dbmanager.link(link_type="agent_skill", primary_id=default_assistant.id, secondary_id=generate_image_skill.id)
        dbmanager.link(
            link_type="workflow_agent", primary_id=default_workflow.id, secondary_id=user_proxy.id, agent_type="sender"
        )
        dbmanager.link(
            link_type="workflow_agent",
            primary_id=default_workflow.id,
            secondary_id=default_assistant.id,
            agent_type="receiver",
        )

        # link agents to travel groupchat agent

        dbmanager.link(link_type="agent_agent", primary_id=travel_groupchat_agent.id, secondary_id=planner_assistant.id)
        dbmanager.link(link_type="agent_agent", primary_id=travel_groupchat_agent.id, secondary_id=local_assistant.id)
        dbmanager.link(
            link_type="agent_agent", primary_id=travel_groupchat_agent.id, secondary_id=language_assistant.id
        )
        dbmanager.link(link_type="agent_agent", primary_id=travel_groupchat_agent.id, secondary_id=user_proxy.id)
        dbmanager.link(link_type="agent_model", primary_id=travel_groupchat_agent.id, secondary_id=gpt_4_model.id)
        dbmanager.link(link_type="agent_model", primary_id=planner_assistant.id, secondary_id=gpt_4_model.id)
        dbmanager.link(link_type="agent_model", primary_id=local_assistant.id, secondary_id=gpt_4_model.id)
        dbmanager.link(link_type="agent_model", primary_id=language_assistant.id, secondary_id=gpt_4_model.id)

        dbmanager.link(
            link_type="workflow_agent", primary_id=travel_workflow.id, secondary_id=user_proxy.id, agent_type="sender"
        )
        dbmanager.link(
            link_type="workflow_agent",
            primary_id=travel_workflow.id,
            secondary_id=travel_groupchat_agent.id,
            agent_type="receiver",
        )
        logger.info("Successfully initialized database with Default and Travel Planning Workflows")
