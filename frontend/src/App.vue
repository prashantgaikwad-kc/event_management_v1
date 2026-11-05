
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
  <div class="portal-shell">
    <header class="site-header">
      <div class="site-header-inner">
        <button class="brand" type="button" @click="showingGateScanner = false; showingOrganizerDashboard = false; showingMyTickets = false; showingMyRegistrations = false; selectedTicket = null; selectedEvent = null">
          <span class="brand-mark">E</span><span>Event<span class="brand-accent">Portal</span></span>
        </button>
        <nav class="site-nav" aria-label="Main navigation">
          <button :class="{ active: !showingMyTickets && !showingMyRegistrations && !showingGateScanner && !showingOrganizerDashboard }" @click="showingMyTickets = false; showingMyRegistrations = false; showingGateScanner = false; showingOrganizerDashboard = false; selectedTicket = null; selectedEvent = null">Explore</button>
          <button :class="{ active: showingMyRegistrations }" @click="showingMyRegistrations = true; showingMyTickets = false; showingGateScanner = false; showingOrganizerDashboard = false">Registrations</button>
          <button :class="{ active: showingMyTickets }" @click="showingMyTickets = true; showingMyRegistrations = false; showingGateScanner = false; showingOrganizerDashboard = false">My Tickets</button>
          <button v-if="canScanTickets" :class="{ active: showingGateScanner }" @click="showingGateScanner = true; showingMyTickets = false; showingMyRegistrations = false; showingOrganizerDashboard = false">Gate Scanner</button>
          <button v-if="canViewOrganizerDashboard" :class="{ active: showingOrganizerDashboard }" @click="showingOrganizerDashboard = true; showingGateScanner = false; showingMyTickets = false; showingMyRegistrations = false">Dashboard</button>
        </nav>
      </div>
    </header>
    <main class="page-container">
      <GateScanner v-if="showingGateScanner && canScanTickets" @back="showingGateScanner = false" />
      <OrganizerDashboard v-else-if="showingOrganizerDashboard && canViewOrganizerDashboard" @back="showingOrganizerDashboard = false" />
      <MyTickets v-else-if="showingMyTickets" @back="showingMyTickets = false" />
      <MyRegistrations v-else-if="showingMyRegistrations" @back="showingMyRegistrations = false" />
      <EventRegistration v-else-if="selectedEvent && selectedTicket" :event="selectedEvent" :ticket="selectedTicket" @back="selectedTicket = null" />
      <template v-else-if="selectedEvent">
        <Button variant="subtle" @click="backToEvents">← Back to Events</Button>
        <section class="event-hero detail-hero">
          <span class="eyebrow">EVENT DETAILS</span>
          <h1>{{ selectedEvent.event_name }}</h1>
          <p>{{ selectedEvent.description || 'Explore event details and find the right ticket for you.' }}</p>
        </section>
        <div class="detail-grid">
          <section class="surface detail-main">
            <h2>About this event</h2>
            <p class="description">{{ selectedEvent.description || 'Event information will be available soon.' }}</p>
            <div class="info-grid">
              <div><span class="info-label">Starts</span><strong>{{ selectedEvent.start_date }}</strong></div>
              <div><span class="info-label">Ends</span><strong>{{ selectedEvent.end_date }}</strong></div>
              <div><span class="info-label">Venue</span><strong>{{ selectedEvent.venue || 'Venue to be announced' }}</strong></div>
              <div><span class="info-label">Availability</span><strong>{{ selectedEvent.remaining_capacity }} seats remaining</strong></div>
            </div>
          </section>
          <aside class="surface detail-aside"><span class="eyebrow">PLAN YOUR VISIT</span><h2>Join this event</h2><p>Choose from the available ticket types below to complete your registration.</p></aside>
        </div>
        <div class="section-heading"><div><span class="eyebrow">YOUR OPTIONS</span><h2>Available tickets</h2></div></div>
        <div v-if="selectedEvent.ticket_types.length" class="card-grid">
          <article v-for="ticket in selectedEvent.ticket_types" :key="ticket.name" class="surface ticket-option">
            <span class="ticket-option-icon">✦</span><h3>{{ ticket.ticket_name }}</h3>
            <p class="price">₹{{ ticket.price }}</p>
            <p class="muted">{{ ticket.remaining_quantity }} available</p>
            <Button variant="solid" :disabled="ticket.remaining_quantity <= 0 || selectedEvent.remaining_capacity <= 0" @click="registerForEvent(ticket)">{{ ticket.remaining_quantity <= 0 ? 'Sold Out' : 'Register Now' }}</Button>
          </article>
        </div>
        <div v-else class="empty-state">Ticket options are not available yet.</div>
      </template>
      <template v-else>
        <section class="event-hero">
          <span class="eyebrow">DISCOVER & CONNECT</span>
          <h1>Experience what’s next.</h1>
          <p>Find events worth showing up for. Explore upcoming experiences and reserve your place in a few simple steps.</p>
          <div class="hero-actions"><span class="hero-pill">✦ &nbsp; Discover upcoming events</span></div>
        </section>
        <div class="section-heading"><div><span class="eyebrow">EXPLORE EVENTS</span><h2>Upcoming events</h2><p>Find your next great experience.</p></div><span v-if="events.length" class="count-pill">{{ events.length }} events</span></div>
        <div v-if="loading" class="empty-state" role="status">Loading events...</div>
        <div v-else-if="error" class="empty-state error-state" role="alert">{{ error }}<div class="mt-4"><Button @click="loadEvents">Try Again</Button></div></div>
        <div v-else-if="!events.length" class="empty-state"><span class="empty-icon">✦</span><h3>No upcoming events yet</h3><p>Check back soon for new experiences.</p></div>
        <div v-else class="card-grid event-grid">
          <article v-for="event in events" :key="event.event_name" class="surface event-card">
            <div class="event-card-art"><span class="event-card-monogram">{{ event.event_name.charAt(0) }}</span><span class="event-card-tag">UPCOMING</span></div>
            <div class="event-card-content"><p class="event-date">{{ event.start_date }}</p><h3>{{ event.event_name }}</h3><p class="event-venue">⌖ &nbsp;{{ event.venue || 'Venue to be announced' }}</p><p class="event-description">{{ event.description }}</p><Button variant="solid" :disabled="!event.route" @click="viewEvent(event.route)">View Details <span aria-hidden="true">→</span></Button></div>
          </article>
        </div>
      </template>
      <p v-if="selectedEvent && loading" class="notice" role="status">Loading event details...</p>
      <p v-if="selectedEvent && error" class="notice error-state" role="alert">{{ error }}</p>
    </main>
  </div>
</template>
