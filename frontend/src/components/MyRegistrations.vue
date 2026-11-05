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
    <Button variant="subtle" @click="emit('back')">← Back</Button>
    <div class="page-header"><span class="eyebrow">YOUR BOOKINGS</span><h1 class="page-title">My Registrations</h1><p class="page-subtitle">Track your bookings and manage upcoming plans.</p></div>
    <p v-if="loading" class="mt-6">Loading registrations...</p>
    <p v-if="error" class="feedback-error mt-6" role="alert">{{ error }}</p>
    <div v-if="!loading && !registrations.length" class="empty-state"><span class="empty-icon">✦</span><h3>No registrations yet</h3><p>Your event bookings will appear here.</p></div>

    <div v-if="!loading && registrations.length" class="mt-6 grid gap-5 md:grid-cols-2">
      <div v-for="registration in registrations" :key="registration.name" class="panel">
        <div class="flex items-start justify-between gap-3"><div><span class="eyebrow">REGISTRATION</span><h3 class="mt-1 font-semibold text-gray-800">{{ registration.event_name }}</h3><p class="mt-1 text-xs text-gray-500">{{ registration.name }}</p></div><span class="status-badge" :data-status="registration.status">{{ registration.status }}</span></div>

        <p class="mt-5"><strong>Ticket Type:</strong> {{ registration.ticket_name }}</p>
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
        <div class="summary-box mt-5 flex items-center justify-between"><span>Total amount</span><strong>₹{{ registration.total_amount }}</strong></div>
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
