"""
Pizza Order State Machine - OrderBot

This example demonstrates the state machine pattern for a pizza ordering system.
A single agent dynamically changes its behavior based on the current_step state,
creating a conversational flow for collecting pizza orders.

Flow:
1. Greeting - Welcome customer and present menu
2. Order Collection - Collect food and drink items
3. Order Type - Ask if pickup or delivery
4. Delivery Address - Collect address (if delivery)
5. Order Summary - Review order and check for additions
6. Payment - Collect payment information
"""

import uuid
from typing import Callable, Literal
from typing_extensions import NotRequired

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse, SummarizationMiddleware
from langchain.messages import HumanMessage, ToolMessage
from langchain.tools import tool, ToolRuntime
from typing import Annotated
from utils.llm import get_llm

from typing import Callable, Literal
from typing_extensions import NotRequired, Annotated

model = get_llm()

def merge_order_items(left: list[dict] | None, right: list[dict] | None) -> list[dict]:
    """How to merge multiple updates to order_items in a single step."""
    return (left or []) + (right or [])


# Define the possible workflow steps
OrderStep = Literal[
    "greeting",
    "order_collection", 
    "order_type",
    "delivery_address",
    "order_summary",
    "payment"
]


class OrderState(AgentState):
    """State for pizza ordering workflow."""    
    current_step: NotRequired[OrderStep]
    order_items: NotRequired[list[dict]]  # List of items with name, size, extras, price
    #order_items: Annotated[NotRequired[list[dict]], merge_order_items]
    order_type: NotRequired[Literal["pickup", "delivery"]]
    delivery_address: NotRequired[str]
    order_total: NotRequired[float]
    payment_confirmed: NotRequired[bool]




# =============================================================================
# Menu Data
# =============================================================================

MENU = """
🍕 **PIZZAS** (Large / Medium / Small):
   • Pepperoni Pizza: $12.95 / $10.00 / $7.00
   • Cheese Pizza: $10.95 / $9.25 / $6.50
   • Eggplant Pizza: $11.95 / $9.75 / $6.75

🍟 **SIDES**:
   • Fries: $4.50 (Large) / $3.50 (Regular)
   • Greek Salad: $7.25

🧀 **TOPPINGS** (Extra):
   • Extra Cheese: $2.00
   • Mushrooms: $1.50
   • Sausage: $3.00
   • Canadian Bacon: $3.50
   • AI Sauce: $1.50
   • Peppers: $1.00

🥤 **DRINKS** (Large / Medium / Small):
   • Coke: $3.00 / $2.00 / $1.00
   • Sprite: $3.00 / $2.00 / $1.00
   • Bottled Water: $5.00
"""

# Price lookup tables
PIZZA_PRICES = {
    "pepperoni": {"large": 12.95, "medium": 10.00, "small": 7.00},
    "cheese": {"large": 10.95, "medium": 9.25, "small": 6.50},
    "eggplant": {"large": 11.95, "medium": 9.75, "small": 6.75},
}

SIDES_PRICES = {
    "fries_large": 4.50,
    "fries_regular": 3.50,
    "greek_salad": 7.25,
}

TOPPING_PRICES = {
    "extra_cheese": 2.00,
    "mushrooms": 1.50,
    "sausage": 3.00,
    "canadian_bacon": 3.50,
    "ai_sauce": 1.50,
    "peppers": 1.00,
}

DRINK_PRICES = {
    "coke": {"large": 3.00, "medium": 2.00, "small": 1.00},
    "sprite": {"large": 3.00, "medium": 2.00, "small": 1.00},
    "bottled_water": 5.00,
}


# =============================================================================
# Tools
# =============================================================================

@tool
def start_order(
    runtime: ToolRuntime[None, OrderState],
) -> Command:
    """Start taking the customer's order after greeting. Call this after greeting the customer."""
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content="Ready to take order. Order collection started.",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "current_step": "order_collection",
            "order_items": [],
            "order_total": 0.0,
        }
    )


@tool
def add_item(
    item_name: str,
    size: str,
    quantity: int,
    extras: list[str],
    price: float,
    runtime: ToolRuntime[None, OrderState],
) -> Command:
    """
    Add an item to the customer's order.
    
    Args:
        item_name: Name of the item (e.g., "Pepperoni Pizza", "Coke")
        size: Size of the item (e.g., "large", "medium", "small", "regular")
        quantity: Number of this item
        extras: List of extra toppings (for pizzas)
        price: Total price for this item including extras
    """
    current_items = runtime.state.get("order_items", [])
    current_total = runtime.state.get("order_total", 0.0)
    
    new_item = {
        "name": item_name,
        "size": size,
        "quantity": quantity,
        "extras": extras,
        "price": price,
    }
    
    updated_items = current_items + [new_item]
    updated_total = current_total + (price * quantity)
    
    extras_str = f" with {', '.join(extras)}" if extras else ""
    
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=f"Added: {quantity}x {size} {item_name}{extras_str} (${price:.2f} each). Running total: ${updated_total:.2f}",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "order_items": updated_items,
            "order_total": updated_total,
        }
    )


@tool
def remove_item(
    item_index: int,
    runtime: ToolRuntime[None, OrderState],
) -> Command:
    """
    Remove an item from the order by its position (1-indexed).
    
    Args:
        item_index: Position of item to remove (1 for first item, 2 for second, etc.)
    """
    current_items = runtime.state.get("order_items", [])
    
    if item_index < 1 or item_index > len(current_items):
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Invalid item number. Order has {len(current_items)} items.",
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
        )
    
    removed_item = current_items[item_index - 1]
    updated_items = current_items[:item_index - 1] + current_items[item_index:]
    
    # Recalculate total
    updated_total = sum(item["price"] * item["quantity"] for item in updated_items)
    
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=f"Removed: {removed_item['name']}. New total: ${updated_total:.2f}",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "order_items": updated_items,
            "order_total": updated_total,
        }
    )


@tool
def finish_order_collection(
    runtime: ToolRuntime[None, OrderState],
) -> Command:
    """Move to ask about pickup or delivery after customer is done ordering items."""
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content="Order collection complete. Now asking about pickup or delivery.",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "current_step": "order_type",
        }
    )


@tool
def set_order_type(
    order_type: Literal["pickup", "delivery"],
    runtime: ToolRuntime[None, OrderState],
) -> Command:
    """
    Record whether this is a pickup or delivery order.
    
    Args:
        order_type: Either "pickup" or "delivery"
    """
    next_step = "delivery_address" if order_type == "delivery" else "order_summary"
    
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=f"Order type set to: {order_type}",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "order_type": order_type,
            "current_step": next_step,
        }
    )


@tool
def set_delivery_address(
    address: str,
    runtime: ToolRuntime[None, OrderState],
) -> Command:
    """
    Record the delivery address.
    
    Args:
        address: Full delivery address
    """
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=f"Delivery address recorded: {address}",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "delivery_address": address,
            "current_step": "order_summary",
        }
    )


@tool
def confirm_order(
    runtime: ToolRuntime[None, OrderState],
) -> Command:
    """Customer confirms the order is complete and ready to pay."""
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content="Order confirmed! Moving to payment.",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "current_step": "payment",
        }
    )


@tool
def add_more_items(
    runtime: ToolRuntime[None, OrderState],
) -> Command:
    """Customer wants to add more items to their order."""
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content="Going back to add more items.",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "current_step": "order_collection",
        }
    )


@tool
def process_payment(
    payment_method: str,
    runtime: ToolRuntime[None, OrderState],
) -> Command:
    """
    Process the customer's payment (simulated).
    
    Args:
        payment_method: How the customer will pay (e.g., "credit card", "cash", "debit")
    """
    order_total = runtime.state.get("order_total", 0.0)
    order_type = runtime.state.get("order_type", "pickup")
    
    # Add tax (8.5%)
    tax = order_total * 0.085
    final_total = order_total + tax
    
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=f"Payment processed via {payment_method}. Subtotal: ${order_total:.2f}, Tax: ${tax:.2f}, Total: ${final_total:.2f}. Order placed successfully!",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "payment_confirmed": True,
        }
    )


@tool
def go_back_to_order(
    runtime: ToolRuntime[None, OrderState],
) -> Command:
    """Go back to modify the order."""
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content="Going back to order collection.",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "current_step": "order_collection",
        }
    )


# =============================================================================
# Prompts for each step
# =============================================================================

GREETING_PROMPT = f"""You are OrderBot 🍕, a friendly automated ordering assistant for Mario's Pizza.

CURRENT STEP: Greeting

Your job is to:
1. Give a warm, friendly greeting
2. Let the customer know you're here to help them order
3. Show them the menu
4. Use the start_order tool when they're ready to order

Be conversational, friendly, and upbeat! Use emojis occasionally.

Here's the menu to share:
{MENU}

After greeting and showing the menu, wait for the customer to indicate they want to order, then use start_order."""

ORDER_COLLECTION_PROMPT = f"""You are OrderBot 🍕, a friendly pizza ordering assistant.

CURRENT STEP: Order Collection
CURRENT ORDER: {{order_items}}
CURRENT TOTAL: ${{order_total:.2f}}

At this step, you need to:
1. Help the customer choose items from the menu
2. For pizzas: ALWAYS clarify the size (small, medium, large)
3. For pizzas: Ask about extra toppings
4. For fries: Ask if they want large or regular
5. For drinks (except bottled water): Ask for size (small, medium, large)
6. Use add_item to add each item with correct price
7. When they're done ordering, use finish_order_collection

PRICING REFERENCE:
{MENU}

IMPORTANT: 
- Calculate prices correctly including extras
- Be conversational and friendly
- Confirm each item as you add it
- If customer says they're done ordering or that's all, use finish_order_collection"""

ORDER_TYPE_PROMPT = """You are OrderBot 🍕, a friendly pizza ordering assistant.

CURRENT STEP: Pickup or Delivery
CURRENT ORDER: {order_items}
ORDER TOTAL: ${order_total:.2f}

At this step, you need to:
1. Ask if this is for pickup or delivery
2. Use set_order_type to record their answer

Keep it brief and friendly!"""

DELIVERY_ADDRESS_PROMPT = """You are OrderBot 🍕, a friendly pizza ordering assistant.

CURRENT STEP: Delivery Address
ORDER TYPE: Delivery 🚗

At this step, you need to:
1. Ask for their complete delivery address
2. Get street address, city, and any apartment/unit number
3. Use set_delivery_address to record the address

Make sure to get a complete, deliverable address!"""

ORDER_SUMMARY_PROMPT = """You are OrderBot 🍕, a friendly pizza ordering assistant.

CURRENT STEP: Order Summary & Final Check
CURRENT ORDER: {order_items}
ORDER TOTAL: ${order_total:.2f}
ORDER TYPE: {order_type}
DELIVERY ADDRESS: {delivery_address}

At this step, you need to:
1. Summarize the complete order with all items and prices
2. Show the subtotal (tax will be added at payment)
3. Confirm the order type (pickup/delivery) and address if delivery
4. Ask if they'd like to add anything else
5. If they want to add more → use add_more_items
6. If order is complete → use confirm_order

Format the order summary nicely and make it easy to read!"""

PAYMENT_PROMPT = """You are OrderBot 🍕, a friendly pizza ordering assistant.

CURRENT STEP: Payment 💳
CURRENT ORDER: {order_items}
ORDER TOTAL: ${order_total:.2f}
ORDER TYPE: {order_type}
DELIVERY ADDRESS: {delivery_address}

At this step, you need to:
1. Show the final total with tax (8.5%)
2. Ask how they'd like to pay (credit card, debit, cash)
3. Use process_payment to complete the order

Note: If they want to change their order, use go_back_to_order.

After payment, thank them and:
- For pickup: Tell them the order will be ready in 15-20 minutes
- For delivery: Tell them delivery will be 30-45 minutes"""


# =============================================================================
# Step Configuration
# =============================================================================

STEP_CONFIG = {
    "greeting": {
        "prompt": GREETING_PROMPT,
        "tools": [start_order],
        "requires": [],
    },
    "order_collection": {
        "prompt": ORDER_COLLECTION_PROMPT,
        "tools": [add_item, remove_item, finish_order_collection],
        "requires": [],
    },
    "order_type": {
        "prompt": ORDER_TYPE_PROMPT,
        "tools": [set_order_type, go_back_to_order],
        "requires": ["order_items"],
    },
    "delivery_address": {
        "prompt": DELIVERY_ADDRESS_PROMPT,
        "tools": [set_delivery_address, go_back_to_order],
        "requires": ["order_type"],
    },
    "order_summary": {
        "prompt": ORDER_SUMMARY_PROMPT,
        "tools": [confirm_order, add_more_items],
        "requires": ["order_items", "order_type"],
    },
    "payment": {
        "prompt": PAYMENT_PROMPT,
        "tools": [process_payment, go_back_to_order],
        "requires": ["order_items", "order_type"],
    },
}


# =============================================================================
# Middleware
# =============================================================================

@wrap_model_call
def apply_step_config(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ModelResponse:
    """Configure agent behavior based on the current step."""
    # Get current step (defaults to greeting for first interaction)
    current_step = request.state.get("current_step", "greeting")
    
    # Look up step configuration
    step_config = STEP_CONFIG[current_step]
    
    # Prepare format values with defaults
    format_values = {
        "order_items": request.state.get("order_items", []),
        "order_total": request.state.get("order_total", 0.0),
        "order_type": request.state.get("order_type", "not set"),
        "delivery_address": request.state.get("delivery_address", "N/A"),
    }
    
    # Format prompt with state values
    system_prompt = step_config["prompt"].format(**format_values)
    
    # Inject system prompt and step-specific tools
    request = request.override(
        system_prompt=system_prompt,
        tools=step_config["tools"],
    )
    
    return handler(request)


# =============================================================================
# Create Agent
# =============================================================================

# Collect all tools from all step configurations
all_tools = [
    start_order,
    add_item,
    remove_item,
    finish_order_collection,
    set_order_type,
    set_delivery_address,
    confirm_order,
    add_more_items,
    process_payment,
    go_back_to_order,
]

# Create the agent with step-based configuration and summarization
agent = create_agent(
    model,
    tools=all_tools,
    state_schema=OrderState,
    middleware=[
        apply_step_config,
        SummarizationMiddleware(
            model=model,
            trigger=("tokens", 4000),
            keep=("messages", 10)
        )
    ],
    checkpointer=InMemorySaver(),
)


# =============================================================================
# Interactive Chat Loop
# =============================================================================

if __name__ == "__main__":
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    print("=" * 60)
    print("🍕 Welcome to Mario's Pizza - OrderBot")
    print("=" * 60)
    print("Start chatting to place your order!")
    print("Type 'quit' or 'exit' to end the conversation.")
    print("Type 'state' to see your current order state.")
    print("Type 'menu' to see the menu again.")
    print("=" * 60)
    print()

    # Start the conversation with a greeting
    result = agent.invoke(
        {"messages": [HumanMessage("Hi, I'd like to order some pizza")]},
        config
    )
    
    # Print the greeting
    for msg in reversed(result["messages"]):
        if hasattr(msg, "content") and msg.type == "ai" and msg.content:
            print(f"🤖 OrderBot: {msg.content}\n")
            break

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nThank you for ordering! Goodbye! 👋🍕")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit"):
            print("\nThank you for ordering! Goodbye! 👋🍕")
            break

        if user_input.lower() == "menu":
            print(MENU)
            continue

        if user_input.lower() == "state":
            snapshot = agent.get_state(config)
            print(f"\n📊 Current Step: {snapshot.values.get('current_step', 'greeting')}")
            print(f"   Order Type: {snapshot.values.get('order_type', 'not set')}")
            print(f"   Delivery Address: {snapshot.values.get('delivery_address', 'N/A')}")
            print(f"   Order Items: {snapshot.values.get('order_items', [])}")
            print(f"   Order Total: ${snapshot.values.get('order_total', 0.0):.2f}")
            print(f"   Payment Confirmed: {snapshot.values.get('payment_confirmed', False)}\n")
            continue

        result = agent.invoke(
            {"messages": [HumanMessage(user_input)]},
            config
        )

        # Print the last AI response
        for msg in reversed(result["messages"]):
            if hasattr(msg, "content") and msg.type == "ai" and msg.content:
                print(f"\n🤖 OrderBot: {msg.content}\n")
                break
