from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker



with workflow.unsafe.imports_passed_through():
    from app.database.session import Base




@workflow.defn
class ProductSyncWorkflow:
    """
    Workflow for syncing products from various sources.
    """

    @workflow.run
    async def run(
            self,
            sync_input: str,
    ) -> Dict[str, Any]:
        """
        Run the product sync workflow.

        Args:
            sync_input: Product sync input containing source configuration and products

        Returns:
            Dictionary with sync result
        """
        pass

# While we could use multiple parameters in the activity, Temporal strongly
# encourages using a single dataclass instead which can have fields added to it
# in a backwards-compatible way.
@dataclass
class ComposeGreetingInput:
    greeting: str
    name: str


# Basic activity that logs and does string concatenation
@activity.defn
async def compose_greeting(input: ComposeGreetingInput) -> str:
    activity.logger.info("Running activity with parameter %s" % input)
    return f"{input.greeting}, {input.name}!"


# Basic workflow that logs and invokes an activity
@workflow.defn
class GreetingWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        workflow.logger.info("Running workflow with parameter %s" % name)
        return await workflow.execute_activity(
            compose_greeting,
            ComposeGreetingInput("Hello", name),
            start_to_close_timeout=timedelta(seconds=10),
        )


async def main():
    import logging
    logging.basicConfig(level=logging.INFO)

    # Start client
    client = await Client.connect("localhost:7233")

    # Run a worker for the workflow
    async with Worker(
        client,
        task_queue="hello-activity-task-queue",
        workflows=[GreetingWorkflow],
    ):
        pass
        # While the worker is running, use the client to run the workflow and
        # print out its result. Note, in many production setups, the client
        # would be in a completely separate process from the worker.
        # result = await client.execute_workflow(
        #     GreetingWorkflow.run,
        #     "World",
        #     id="hello-activity-workflow-id",
        #     task_queue="hello-activity-task-queue",
        # )
        # print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())