
class StripeEventProcessor:
    def __init__(self, event):
        self.event = event

    def process(self):
        event_type = self.event['type']

        if event_type == 'customer.subscription.created':
            print("Subscription created!")
            return True

        elif event_type == 'invoice.payment_failed':
            print("Payment failed!")
            return False

        return False