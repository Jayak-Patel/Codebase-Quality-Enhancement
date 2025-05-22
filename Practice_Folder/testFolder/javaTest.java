package org.sonar.application.process;

import java.net.ConnectException;
import java.time.Duration;
import java.time.temporal.ChronoUnit;
import java.util.Optional;
import org.elasticsearch.ElasticsearchException;
import org.elasticsearch.cluster.health.ClusterHealthStatus;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.sonar.application.es.EsConnector;
import org.sonar.process.ProcessId;

/**
 * Manages the lifecycle of an Elasticsearch process within the SonarQube application.
 * This class provides functionality to check the operational status of the Elasticsearch node
 * and manage its shutdown.
 */
public class EsManagedProcess extends AbstractManagedProcess {

  private static final Logger LOG = LoggerFactory.getLogger(EsManagedProcess.class);
  private static final Duration WAIT_FOR_UP_DELAY = Duration.of(100, ChronoUnit.MILLIS);
  private static final Duration DEFAULT_WAIT_FOR_UP_TIMEOUT = Duration.of(10, ChronoUnit.MINUTES);

  private final EsConnector esConnector;
  private final Duration waitForUpTimeout;
  private volatile boolean nodeOperational = false;

  /**
   * Constructs an {@code EsManagedProcess} with the specified process, process ID, and Elasticsearch connector.
   *
   * @param process     The process representing the Elasticsearch instance.
   * @param processId   The unique identifier for the process.
   * @param esConnector The connector for interacting with the Elasticsearch cluster.
   */
  public EsManagedProcess(Process process, ProcessId processId, EsConnector esConnector) {
    this(process, processId, esConnector, DEFAULT_WAIT_FOR_UP_TIMEOUT);
  }

  /**
   * Constructs an {@code EsManagedProcess} with the specified process, process ID, Elasticsearch connector, and wait-for-up timeout.
   *
   * @param process           The process representing the Elasticsearch instance.
   * @param processId         The unique identifier for the process.
   * @param esConnector       The connector for interacting with the Elasticsearch cluster.
   * @param waitForUpTimeout  The maximum duration to wait for the Elasticsearch node to become operational.
   */
  EsManagedProcess(Process process, ProcessId processId, EsConnector esConnector, Duration waitForUpTimeout) {
    super(process, processId);
    this.esConnector = esConnector;
    this.waitForUpTimeout = waitForUpTimeout;
  }

  /**
   * Checks if the Elasticsearch node is operational.
   *
   * @return {@code true} if the node is operational; {@code false} otherwise.
   */
  @Override
  public boolean isOperational() {
    if (nodeOperational) {
      return true;
    }

    try {
      if (checkAndSetOperational()) {
        nodeOperational = true;
        return true;
      }
      return false;

    } catch (InterruptedException e) {
      LOG.trace("Interrupted while checking ES node is operational", e);
      Thread.currentThread().interrupt(); // Restore interrupt status
      return false;

    } finally {
      if (nodeOperational) {
        try {
          esConnector.stop();
        } catch (Exception e) {
          LOG.warn("Failed to stop Elasticsearch connector after successful startup check.", e);
        }
      }
    }
  }

  private boolean checkAndSetOperational() throws InterruptedException {
    Status status = waitForOperationalStatus();
    return status == Status.YELLOW || status == Status.GREEN;
  }

  private Status waitForOperationalStatus() throws InterruptedException {
    Status status = checkStatus();
    Duration elapsed = Duration.ZERO;

    while (status == Status.CONNECTION_REFUSED && elapsed.compareTo(waitForUpTimeout) < 0) {
      Thread.sleep(WAIT_FOR_UP_DELAY.toMillis());
      elapsed = elapsed.plus(WAIT_FOR_UP_DELAY);
      status = checkStatus();
    }

    return status;
  }


  private Status checkStatus() {
    try {
      Optional<ClusterHealthStatus> healthStatus = esConnector.getClusterHealthStatus();
      return healthStatus.map(EsManagedProcess::convert).orElse(Status.CONNECTION_REFUSED);
    } catch (ElasticsearchException e) {
      if (e.getRootCause() instanceof ConnectException) {
        return Status.CONNECTION_REFUSED;
      }
      LOG.error("Failed to check Elasticsearch cluster status", e);
      return Status.KO;
    } catch (Exception e) {
      LOG.error("An unexpected error occurred while checking Elasticsearch cluster status", e);
      return Status.KO;
    }
  }

  private static Status convert(ClusterHealthStatus clusterHealthStatus) {
    switch (clusterHealthStatus) {
      case GREEN:
        return Status.GREEN;
      case YELLOW:
        return Status.YELLOW;
      case RED:
        return Status.RED;
      default:
        return Status.KO;
    }
  }

  /**
   * Asks the Elasticsearch process to stop.  This is a hard stop, as Elasticsearch
   * has no concept of a "soft" or graceful shutdown initiated from this level.
   */
  @Override
  public void askForStop() {
    askForHardStop();
  }

  /**
   * Performs a hard stop of the Elasticsearch process.
   */
  @Override
  public void askForHardStop() {
    process.destroy();
  }

  /**
   * Indicates that Elasticsearch process does not support asking for a restart.
   *
   * @return {@code false} always.
   */
  @Override
  public boolean askedForRestart() {
    return false;
  }

  /**
   * Acknowledges a request for restart. This method is a no-op because Elasticsearch doesn't
   * support asking for a restart.
   */
  @Override
  public void acknowledgeAskForRestart() {
    // Nothing to do.
  }

  /**
   * Enumerates the possible status values for the Elasticsearch process.
   */
  enum Status {
    CONNECTION_REFUSED,
    KO, // General error/failure
    RED, // Cluster is unhealthy; some data is unavailable.
    YELLOW, // Cluster is operational but some data is not yet fully replicated.
    GREEN // Cluster is healthy and all data is available.
  }
}
