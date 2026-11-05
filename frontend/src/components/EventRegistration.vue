<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Button, call } from 'frappe-ui'

interface TicketType {
  name: string
  ticket_name: string
  price: number
  remaining_quantity: number
}

interface EventDetails {
  name: string
  event_name: string
}

interface AddOn {
  name: string
  add_on_name: string
  price: number
  selected: boolean
  quantity: number
}

const props = defineProps<{ event: EventDetails; ticket: TicketType }>()
const emit = defineEmits<{ back: [] }>()

const attendeeName = ref('')
const email = ref('')
const mobileNumber = ref('')
const quantity = ref(1)
const addOns = ref<AddOn[]>([])
const loading = ref(false)
const submitting = ref(false)
const error = ref('')
const registrationName = ref('')

const estimatedTotal = computed(() =>
  Number(props.ticket.price) * quantity.value +
  addOns.value.reduce(
    (total, addOn) => total + (addOn.selected ? Number(addOn.price) * addOn.quantity : 0),
    0,
  ),
)

watch(() => props.event.name, async (eventName) => {
  loading.value = true
  error.value = ''
  addOns.value = []
  try {
    const options = await call<{ add_ons: Omit<AddOn, 'selected' | 'quantity'>[] }>(
      'event_management.event_management.web_form.event_registration.event_registration.get_event_options',
      { event: eventName },
    )
    if (props.event.name === eventName) {
      addOns.value = options.add_ons.map((addOn) => ({ ...addOn, selected: false, quantity: 1 }))
    }
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Unable to load add-ons.'
  } finally {
    loading.value = false
  }
}, { immediate: true })

async function submitRegistration() {
  submitting.value = true
  error.value = ''
  try {
    const registration = await call<{ name: string }>(
      'frappe.website.doctype.web_form.web_form.accept',
      {
        web_form: 'event-registration',
        data: JSON.stringify({
          attendee_name: attendeeName.value,
          email: email.value,
          mobile_number: mobileNumber.value,
          event: props.event.name,
          ticket_type: props.ticket.name,
          quantity: quantity.value,
          add_ons: addOns.value
            .filter((addOn) => addOn.selected)
            .map((addOn) => ({ add_on: addOn.name, quantity: addOn.quantity })),
        }),
      },
    )
    registrationName.value = registration.name
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Unable to submit registration.'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div>
    <Button variant="subtle" @click="emit('back')">Back to Event</Button>

    <h2 class="mt-6 text-2xl font-semibold">Register for {{ event.event_name }}</h2>
    <p class="mt-2 text-gray-600">{{ ticket.ticket_name }} · ₹{{ ticket.price }} per ticket</p>

    <p v-if="registrationName" class="mt-6 text-green-700">
      Registration {{ registrationName }} submitted. Status: Pending.
    </p>

    <form v-else class="mt-6 max-w-xl space-y-4 rounded-lg border bg-white p-5" @submit.prevent="submitRegistration">
      <label class="block">
        <span>Attendee Name</span>
        <input v-model="attendeeName" class="mt-1 w-full rounded border p-2" required />
      </label>
      <label class="block">
        <span>Email</span>
        <input v-model="email" type="email" class="mt-1 w-full rounded border p-2" required />
      </label>
      <label class="block">
        <span>Mobile Number</span>
        <input v-model="mobileNumber" type="tel" class="mt-1 w-full rounded border p-2" required />
      </label>
      <label class="block">
        <span>Ticket Quantity</span>
        <input v-model.number="quantity" type="number" min="1" :max="ticket.remaining_quantity" step="1" class="mt-1 w-full rounded border p-2" required />
      </label>

      <div v-if="addOns.length">
        <h3 class="font-semibold">Add-ons</h3>
        <div v-for="addOn in addOns" :key="addOn.name" class="mt-3 flex items-center gap-3">
          <label class="flex flex-1 items-center gap-2">
            <input v-model="addOn.selected" type="checkbox" />
            {{ addOn.add_on_name }} · ₹{{ addOn.price }}
          </label>
          <input v-if="addOn.selected" v-model.number="addOn.quantity" type="number" min="1" step="1" required class="w-20 rounded border p-2" :aria-label="`${addOn.add_on_name} quantity`" />
        </div>
      </div>

      <p v-if="loading">Loading add-ons...</p>
      <p v-if="error" class="text-red-600" role="alert">{{ error }}</p>
      <p class="font-semibold">Estimated total: ₹{{ estimatedTotal }}</p>
      <Button type="submit" variant="solid" :disabled="loading || submitting">
        {{ submitting ? 'Submitting...' : 'Submit Registration' }}
      </Button>
    </form>
  </div>
</template>
