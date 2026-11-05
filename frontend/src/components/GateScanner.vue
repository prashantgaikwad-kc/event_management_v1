<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { Button, call } from 'frappe-ui'
import QrScanner from 'qr-scanner'

const emit = defineEmits<{ back: [] }>()
const video = ref<HTMLVideoElement | null>(null)
const credential = ref('')
const scanning = ref(false)
const submitting = ref(false)
const message = ref('')
const error = ref('')
interface TicketMatch {
  name: string
  attendee_name: string
  event: string
  ticket_type: string
  status: string
}
const searchQuery = ref('')
const matches = ref<TicketMatch[]>([])
const hasSearched = ref(false)
const searching = ref(false)
const checkingIn = ref(false)
const manualMessage = ref('')
const manualError = ref('')
let scanner: QrScanner | null = null

async function searchTickets() {
  if (!searchQuery.value.trim() || searching.value) return
  searching.value = true
  hasSearched.value = false
  matches.value = []
  manualError.value = ''
  try {
    matches.value = await call<TicketMatch[]>(
      'event_management.event_management.doctype.em_ticket.em_ticket.search_tickets',
      { query: searchQuery.value.trim() },
    )
    hasSearched.value = true
  } catch (cause) {
    manualError.value = (cause as Error).message || 'Unable to search tickets.'
  } finally {
    searching.value = false
  }
}

async function manualCheckIn(ticket: TicketMatch) {
  if (ticket.status !== 'Issued' || checkingIn.value) return
  if (!window.confirm(`Check in ${ticket.attendee_name} for ${ticket.event} (${ticket.ticket_type})?`)) return
  checkingIn.value = true
  manualMessage.value = ''
  manualError.value = ''
  try {
    await call('event_management.event_management.doctype.em_ticket.em_ticket.manual_check_in',
      { ticket_id: ticket.name })
    manualMessage.value = `${ticket.attendee_name} checked in successfully.`
  } catch (cause) {
    manualError.value = (cause as Error).message || 'Unable to check in ticket.'
  } finally {
    checkingIn.value = false
    await searchTickets()
  }
}

function stopScanner() {
  scanner?.destroy()
  scanner = null
  scanning.value = false
}

async function startScanner() {
  if (!video.value || scanning.value || submitting.value) return
  message.value = ''
  error.value = ''
  scanner = new QrScanner(video.value, (result) => {
    if (submitting.value) return
    stopScanner()
    credential.value = result.data
    submitTicket()
  }, { preferredCamera: 'environment', returnDetailedScanResult: true })
  try {
    await scanner.start()
    scanning.value = true
  } catch (cause) {
    stopScanner()
    error.value = cause instanceof Error ? cause.message : 'Unable to start camera.'
  }
}

async function submitTicket() {
  if (submitting.value || !credential.value.trim()) return
  stopScanner()
  submitting.value = true
  message.value = ''
  error.value = ''
  try {
    const result = await call<{ ticket: string; status: string }>(
      'event_management.event_management.doctype.em_ticket.em_ticket.check_in_ticket',
      { qr_credential: credential.value.trim() },
    )
    message.value = result.status === 'Already Checked In'
      ? `Ticket ${result.ticket} was already checked in.`
      : `Ticket ${result.ticket} checked in successfully.`
    credential.value = ''
  } catch (cause) {
    const failure = cause as Error & { exc_type?: string }
    error.value = failure.exc_type === 'PermissionError'
      ? 'You are not permitted to check in tickets.'
      : failure.message || 'Invalid ticket credential.'
  } finally {
    submitting.value = false
  }
}

onBeforeUnmount(stopScanner)
</script>

<template>
  <div>
    <Button variant="subtle" @click="emit('back')">Back</Button>
    <h2 class="mt-6 text-2xl font-semibold">Gate Scanner</h2>

    <div class="mt-6 max-w-md rounded-lg border bg-white p-5 shadow-sm">
      <video ref="video" class="w-full rounded bg-gray-100" playsinline muted></video>
      <div class="mt-3 flex gap-2">
        <Button v-if="!scanning" :disabled="submitting" @click="startScanner">Start Camera</Button>
        <Button v-else variant="subtle" @click="stopScanner">Stop Camera</Button>
      </div>

      <label for="ticket-credential" class="mt-5 block font-medium">Ticket credential</label>
      <input
        id="ticket-credential"
        v-model="credential"
        type="text"
        autocomplete="off"
        class="mt-2 w-full rounded border px-3 py-2"
        placeholder="Paste or scan a ticket credential"
        :disabled="submitting"
        @keyup.enter="submitTicket"
      />
      <Button class="mt-3" variant="solid" :disabled="submitting || !credential.trim()" @click="submitTicket">
        {{ submitting ? 'Checking in...' : 'Check In' }}
      </Button>

      <p v-if="message" class="mt-4 text-green-700" role="status">{{ message }}</p>
      <p v-if="error" class="mt-4 text-red-600" role="alert">{{ error }}</p>
    </div>

    <div class="mt-6 max-w-3xl rounded-lg border bg-white p-5 shadow-sm">
      <h3 class="text-lg font-semibold">Manual Check-in</h3>
      <label for="attendee-search" class="mt-4 block font-medium">Attendee name or email</label>
      <div class="mt-2 flex gap-2">
        <input id="attendee-search" v-model="searchQuery" type="search" autocomplete="off"
          class="w-full rounded border px-3 py-2" placeholder="Search attendees"
          @keyup.enter="searchTickets" />
        <Button :disabled="searching || checkingIn || !searchQuery.trim()" @click="searchTickets">
          {{ searching ? 'Searching...' : 'Search' }}
        </Button>
      </div>
      <p v-if="manualMessage" class="mt-4 text-green-700" role="status">{{ manualMessage }}</p>
      <p v-if="manualError" class="mt-4 text-red-600" role="alert">{{ manualError }}</p>
      <div v-if="matches.length" class="mt-4 overflow-x-auto">
        <table class="w-full text-left text-sm">
          <thead><tr class="border-b"><th class="p-2">Attendee</th><th class="p-2">Event</th><th class="p-2">Ticket type</th><th class="p-2">Status</th><th class="p-2">Action</th></tr></thead>
          <tbody>
            <tr v-for="ticket in matches" :key="ticket.name" class="border-b">
              <td class="p-2">{{ ticket.attendee_name }}</td>
              <td class="p-2">{{ ticket.event }}</td>
              <td class="p-2">{{ ticket.ticket_type }}</td>
              <td class="p-2">{{ ticket.status }}</td>
              <td class="p-2"><Button :disabled="ticket.status !== 'Issued' || checkingIn" @click="manualCheckIn(ticket)">Check In</Button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else-if="hasSearched" class="mt-4 text-gray-600">No matching tickets.</p>
    </div>
  </div>
</template>
