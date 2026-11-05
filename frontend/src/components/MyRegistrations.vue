<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Button, call } from 'frappe-ui'

interface AddOn {
  add_on: string
  add_on_name: string
  quantity: number
  amount: number
}

interface Registration {
  name: string
  event: string
  event_name: string
  ticket_type: string
  ticket_name: string
  quantity: number
  add_ons: AddOn[]
  total_amount: number
  status: string
  can_cancel: boolean
}

const emit = defineEmits<{ back: [] }>()
const registrations = ref<Registration[]>([])
const loading = ref(true)
const cancelling = ref('')
const error = ref('')

async function loadRegistrations() {
  loading.value = true
  error.value = ''
  try {
    registrations.value = await call<Registration[]>(
      'event_management.event_management.doctype.em_registration.em_registration.get_my_registrations',
    )
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Unable to load registrations.'
  } finally {
    loading.value = false
  }
}

async function cancelRegistration(registration: Registration) {
  if (!window.confirm(`Cancel registration ${registration.name}?`)) return
  cancelling.value = registration.name
  error.value = ''
  try {
    await call(
      'event_management.event_management.doctype.em_registration.em_registration.cancel_my_registration',
      { registration: registration.name },
    )
    await loadRegistrations()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Unable to cancel registration.'
  } finally {
    cancelling.value = ''
  }
}

onMounted(loadRegistrations)
</script>

<template>
  <div>
    <Button variant="subtle" @click="emit('back')">Back</Button>
    <h2 class="mt-6 text-2xl font-semibold">My Registrations</h2>
    <p v-if="loading" class="mt-6">Loading registrations...</p>
    <p v-if="error" class="mt-6 text-red-600" role="alert">{{ error }}</p>
    <p v-if="!loading && !registrations.length" class="mt-6">No registrations found.</p>

    <div v-if="!loading && registrations.length" class="mt-6 grid gap-4 md:grid-cols-2">
      <div v-for="registration in registrations" :key="registration.name" class="rounded-lg border bg-white p-5 shadow-sm">
        <h3 class="font-semibold">{{ registration.name }}</h3>
        <p class="mt-2"><strong>Event:</strong> {{ registration.event_name }}</p>
        <p class="mt-1"><strong>Ticket Type:</strong> {{ registration.ticket_name }}</p>
        <p class="mt-1"><strong>Quantity:</strong> {{ registration.quantity }}</p>
        <div class="mt-1">
          <strong>Add-ons:</strong>
          <ul v-if="registration.add_ons.length" class="ml-5 list-disc">
            <li v-for="addOn in registration.add_ons" :key="addOn.add_on">
              {{ addOn.add_on_name }} × {{ addOn.quantity }} · ₹{{ addOn.amount }}
            </li>
          </ul>
          <span v-else> None</span>
        </div>
        <p class="mt-1"><strong>Total Amount:</strong> ₹{{ registration.total_amount }}</p>
        <p class="mt-1"><strong>Status:</strong> {{ registration.status }}</p>
        <Button
          v-if="registration.can_cancel"
          class="mt-4"
          variant="subtle"
          :disabled="!!cancelling"
          @click="cancelRegistration(registration)"
        >
          {{ cancelling === registration.name ? 'Cancelling...' : 'Cancel Registration' }}
        </Button>
      </div>
    </div>
  </div>
</template>
