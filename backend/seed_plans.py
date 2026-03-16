from app.database.db import SessionLocal
from app.models.plan import Plan, PlanStrategy
from app.models.bot import Bot
from app.models.user import User

def seed_plans():
    db = SessionLocal()
    try:
        # 1. Create Plans
        plans_data = [
            {"name": "Starter", "max_strategies": 3, "price_usd": 0.0},
            {"name": "Pro", "max_strategies": 10, "price_usd": 49.0},
            {"name": "Elite", "max_strategies": 99, "price_usd": 99.0},
        ]

        created_plans = {}
        for p in plans_data:
            existing = db.query(Plan).filter(Plan.name == p["name"]).first()
            if not existing:
                plan = Plan(name=p["name"], max_strategies=p["max_strategies"], price_usd=p["price_usd"])
                db.add(plan)
                db.flush()
                created_plans[p["name"]] = plan
                print(f"Created plan: {p['name']}")
            else:
                created_plans[p["name"]] = existing
                # Update limits if they changed
                existing.max_strategies = p["max_strategies"]
                existing.price_usd = p["price_usd"]
                print(f"Plan {p['name']} already exists, updated limits.")

        # 2. Link all existing bots to all plans (by default, everything is available in Starter for now)
        all_bots = db.query(Bot).all()
        for bot in all_bots:
            for plan_name, plan in created_plans.items():
                # Check if link exists
                link = db.query(PlanStrategy).filter(
                    PlanStrategy.plan_id == plan.id,
                    PlanStrategy.bot_id == bot.id
                ).first()
                if not link:
                    db.add(PlanStrategy(plan_id=plan.id, bot_id=bot.id))
                    print(f"Linked bot {bot.slug} to plan {plan_name}")

        # 3. Assign Starter plan to all existing users who don't have one
        starter_plan = created_plans["Starter"]
        users_without_plan = db.query(User).filter(User.plan_id == None).all()
        for u in users_without_plan:
            u.plan_id = starter_plan.id
            print(f"Assigned Starter plan to user: {u.email}")

        db.commit()
        print("Seeding completed successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding plans: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_plans()
