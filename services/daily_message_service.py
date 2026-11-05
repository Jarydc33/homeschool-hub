# services/daily_message_service.py

# Motivation and kindness, mixed so that neither runs for long.
MESSAGES = [
    "Small steps still move you forward. Take one today.",
    "Say something kind to someone in your family today.",
    "A mistake just means you're trying something new.",
    "Ask someone how their day is going, and really listen.",
    "You don't have to be perfect. You just have to keep going.",
    "Help with one thing today before anyone asks you to.",
    "The hard part is usually starting. You can do that.",
    "Tell someone one thing you appreciate about them.",
    "Your brain grows when the work feels hard.",
    "Share something today, even if it's just a smile.",
    "Today is a good day to learn something surprising.",
    "Be patient with someone who's still learning. So are you.",
    "Finish one thing you've been putting off. It will feel great.",
    "Write or say a thank-you to someone who helped you.",
    "It's okay to ask for help. Smart people do it all the time.",
    "Include someone who might be feeling left out.",
    "Practice beats talent when talent doesn't practice.",
    "Let someone else go first today.",
    "If you can't do it yet, the important word is yet.",
    "Give someone a real compliment today.",
    "Pick the hardest thing first, and the rest will feel easier.",
    "Clean up something that isn't your mess.",
    "Curious questions are some of the best ones. Ask one today.",
    "Forgive someone for a small mistake today, including yourself.",
    "Progress is progress, even when it's slow.",
    "Do something nice for someone without telling anyone.",
    "Look back at something that used to be hard. You did that.",
    "Use a gentle voice, even when you're frustrated.",
    "Try once more before you decide it's too hard.",
    "Encourage someone who's having a tough day.",
    "Every expert started out as a beginner.",
    "Make someone laugh today.",
    "Focus on what you can do right now, not everything at once.",
    "Offer to help a brother, sister, or friend today.",
    "You're capable of more than you think.",
    "Notice something good someone did, and tell them.",
    "Take a deep breath. You can start again at any moment.",
    "Be the reason someone smiles today.",
    "Doing your best looks different every day, and that's okay.",
    "Treat others the way you'd like to be treated.",
]


class DailyMessageService:

    @staticmethod
    def get_message(day):
        """
        Returns the message for a date. It stays the same all day and changes
        the next, working through the whole list before repeating.
        """

        return MESSAGES[
            day.toordinal() % len(MESSAGES)
        ]
