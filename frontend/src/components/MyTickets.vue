<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Button, call } from 'frappe-ui'
import QRCode from 'qrcode'

interface Ticket {
  name: string
  event: string
  ticket_type: string
  attendee_name: string
  status: string
  checked_in_at: string | null
  qr_credential: string | null
  qr_image?: string
}

const emit = defineEmits<{ back: [] }>()
const tickets = ref<Ticket[]>([])
const loading = ref(true)
const error = ref('')

async function loadTickets() {
  loading.value = true
  error.value = ''
  try {
    const fetchedTickets = await call<Ticket[]>(
      'event_management.event_management.doctype.em_ticket.em_ticket.get_my_tickets',
    )
    tickets.value = await Promise.all(
      fetchedTickets.map(async (ticket) => {
        if (ticket.status === 'Issued' && ticket.qr_credential?.trim()) {
          ticket.qr_image = await QRCode.toDataURL(ticket.qr_credential)
        }
        return ticket
      }),
    )
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Unable to load tickets.'
  } finally {
    loading.value = false
  }
}

onMounted(loadTickets)
</script>

<template>
  <div>
    <Button variant="subtle" @click="emit('back')">Back</Button>
    <h2 class="mt-6 text-2xl font-semibold">My Tickets</h2>

    <p v-if="loading" class="mt-6">Loading tickets...</p>
    <p v-else-if="error" class="mt-6 text-red-600" role="alert">{{ error }}</p>
    <p v-else-if="!tickets.length" class="mt-6">No tickets found</p>

    <div v-else class="mt-6 grid gap-4 md:grid-cols-2">
      <div v-for="ticket in tickets" :key="ticket.name" class="rounded-lg border bg-white p-5 shadow-sm">
        <h3 class="font-semibold">{{ ticket.name }}</h3>
        <p class="mt-2"><strong>Event:</strong> {{ ticket.event }}</p>
        <p class="mt-1"><strong>Ticket Type:</strong> {{ ticket.ticket_type }}</p>
        <p class="mt-1"><strong>Attendee:</strong> {{ ticket.attendee_name }}</p>
        <p class="mt-1"><strong>Status:</strong> {{ ticket.status }}</p>
        <img
          v-if="ticket.status === 'Issued' && ticket.qr_image"
          :src="ticket.qr_image"
          :alt="`QR code for ticket ${ticket.name}`"
          class="mt-3 h-40 w-40"
        />
        <p v-if="ticket.checked_in_at" class="mt-1">
          <strong>Checked in at:</strong> {{ ticket.checked_in_at }}
        </p>
      </div>
    </div>
  </div>
</template>
