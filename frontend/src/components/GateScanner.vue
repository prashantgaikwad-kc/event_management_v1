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
let scanner: QrScanner | null = null

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
  </div>
</template>
