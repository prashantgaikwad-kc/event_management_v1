
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Button, call } from 'frappe-ui'
import EventRegistration from './components/EventRegistration.vue'
import MyTickets from './components/MyTickets.vue'
import MyRegistrations from './components/MyRegistrations.vue'
import GateScanner from './components/GateScanner.vue'
import OrganizerDashboard from './components/OrganizerDashboard.vue'

interface TicketType {
  name: string
  ticket_name: string
  price: number
  remaining_quantity: number
}

interface EventDetails {
  name: string
  event_name: string
  description: string
  venue: string
  start_date: string
  end_date: string
  route: string | null
  remaining_capacity: number
  ticket_types: TicketType[]
}

interface EventSummary {
  event_name: string
  venue: string
  start_date: string
  description: string
  route: string | null
}

const events = ref<EventSummary[]>([])
const selectedEvent = ref<EventDetails | null>(null)
const selectedTicket = ref<TicketType | null>(null)
const showingMyTickets = ref(false)
const showingMyRegistrations = ref(false)
const showingGateScanner = ref(false)
const showingOrganizerDashboard = ref(false)
const canScanTickets = ref(false)
const canViewOrganizerDashboard = ref(false)
const loading = ref(false)
const error = ref('')

async function loadEvents() {
  loading.value = true
  error.value = ''

  try {
    const response = await fetch(
      '/api/method/event_management.www.events.get_upcoming_events'
    )

    if (!response.ok) {
      throw new Error('Failed to load events')
    }

    const data = await response.json()
    events.value = data.message || []
  } catch {
    error.value = 'Unable to load events'
  } finally {
    loading.value = false
  }
}

async function viewEvent(route: string | null) {
  if (!route) return

  loading.value = true
  error.value = ''

  try {
    const response = await fetch(
      '/api/method/event_management.www.events.get_event_details?route=' +
        encodeURIComponent(route)
    )

    if (!response.ok) {
      throw new Error('Failed to load event details')
    }

    const data = await response.json()

    if (!data.message) {
      throw new Error('Event not found')
    }

    selectedEvent.value = data.message
  } catch {
    error.value = 'Unable to load event details'
  } finally {
    loading.value = false
  }
}

function backToEvents() {
  selectedEvent.value = null
  loadEvents()
}

function registerForEvent(ticket: TicketType) {
  selectedTicket.value = ticket
}

onMounted(() => {
  loadEvents()
  call<string[]>('frappe.core.doctype.user.user.get_current_user_roles').then((roles) => {
    canScanTickets.value = roles.includes('EM Gate Staff') || roles.includes('System Manager')
    canViewOrganizerDashboard.value = roles.includes('EM Organizer') || roles.includes('System Manager')
  }).catch(() => {
    canScanTickets.value = false
    canViewOrganizerDashboard.value = false
  })
})
</script>

<template>
  <div class="min-h-screen bg-gray-50 p-6">
    <div class="mx-auto max-w-6xl">
      <GateScanner v-if="showingGateScanner && canScanTickets" @back="showingGateScanner = false" />
      <OrganizerDashboard v-else-if="showingOrganizerDashboard && canViewOrganizerDashboard" @back="showingOrganizerDashboard = false" />
      <MyTickets v-else-if="showingMyTickets" @back="showingMyTickets = false" />
      <MyRegistrations v-else-if="showingMyRegistrations" @back="showingMyRegistrations = false" />
      <EventRegistration
        v-else-if="selectedEvent && selectedTicket"
        :event="selectedEvent"
        :ticket="selectedTicket"
        @back="selectedTicket = null"
      />

      <template v-else-if="selectedEvent">
        <Button variant="subtle" @click="backToEvents">
          Back to Events
        </Button>

        <h1 class="mt-6 text-3xl font-semibold">
          {{ selectedEvent.event_name }}
        </h1>

        <p class="mt-3 text-gray-600">
          {{ selectedEvent.description }}
        </p>

        <div class="mt-5 rounded-lg border bg-white p-5">
          <p>
            <strong>Venue:</strong> {{ selectedEvent.venue }}
          </p>

          <p class="mt-2">
            <strong>Starts:</strong> {{ selectedEvent.start_date }}
          </p>

          <p class="mt-2">
            <strong>Ends:</strong> {{ selectedEvent.end_date }}
          </p>

          <p class="mt-2">
            <strong>Remaining Seats:</strong>
            {{ selectedEvent.remaining_capacity }}
          </p>
        </div>

        <h2 class="mt-8 text-xl font-semibold">
          Ticket Types
        </h2>

        <div class="mt-4 grid gap-4 md:grid-cols-3">
          <div
            v-for="ticket in selectedEvent.ticket_types"
            :key="ticket.name"
            class="rounded-lg border bg-white p-5"
          >
            <h3 class="font-semibold">
              {{ ticket.ticket_name }}
            </h3>

            <p class="mt-2 text-lg">
              ₹{{ ticket.price }}
            </p>

            <p class="mt-2 text-sm text-gray-600">
              Available: {{ ticket.remaining_quantity }}
            </p>

            <Button
              class="mt-4"
              variant="solid"
              :disabled="
                ticket.remaining_quantity <= 0 ||
                selectedEvent.remaining_capacity <= 0
              "
              @click="registerForEvent(ticket)"
            >
              Register
            </Button>
          </div>
        </div>
      </template>

      <template v-else>
        <h1 class="text-2xl font-semibold">
          Event Management
        </h1>

        <p class="mt-2 text-gray-600">
          Discover upcoming events
        </p>

        <Button class="mt-4" variant="subtle" @click="showingMyTickets = true">
          My Tickets
        </Button>
        <Button class="ml-2 mt-4" variant="subtle" @click="showingMyRegistrations = true">
          My Registrations
        </Button>
        <Button v-if="canScanTickets" class="ml-2 mt-4" variant="subtle" @click="showingGateScanner = true">
          Gate Scanner
        </Button>
        <Button v-if="canViewOrganizerDashboard" class="ml-2 mt-4" variant="subtle" @click="showingOrganizerDashboard = true">
          Organizer Dashboard
        </Button>

        <p v-if="!loading && error" class="mt-6 text-red-600">
          {{ error }}
        </p>

        <p v-else-if="loading" class="mt-6">
          Loading events...
        </p>

        <p v-else-if="!events.length" class="mt-6">
          No upcoming events found.
        </p>

        <div
          v-else
          class="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3"
        >
          <div
            v-for="event in events"
            :key="event.event_name"
            class="rounded-lg border bg-white p-5 shadow-sm"
          >
            <h2 class="text-lg font-semibold">
              {{ event.event_name }}
            </h2>

            <p class="mt-2 text-sm text-gray-600">
              {{ event.venue }}
            </p>

            <p class="mt-1 text-sm text-gray-600">
              {{ event.start_date }}
            </p>

            <p class="mt-3 text-sm">
              {{ event.description }}
            </p>

            <Button
              class="mt-4"
              variant="solid"
              :disabled="!event.route"
              @click="viewEvent(event.route)"
            >
              View Details
            </Button>
          </div>
        </div>
      </template>

      <p
        v-if="selectedEvent && loading"
        class="mt-6"
      >
        Loading...
      </p>

      <p
        v-if="selectedEvent && error"
        class="mt-6 text-red-600"
      >
        {{ error }}
      </p>
    </div>
  </div>
</template>
